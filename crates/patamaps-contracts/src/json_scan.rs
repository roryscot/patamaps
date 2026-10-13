use crate::ContractError;
use serde::Deserialize;
use std::{collections::HashSet, fmt::Write};

/// Validate complete JSON grammar before I-JSON interpretation. RawValue's
/// iterative grammar checker neither rounds numbers nor rejects UTF-16 escape
/// units. This preserves syntax/duplicate/depth precedence from the reference.
pub(crate) fn validate(bytes: &[u8], max_depth: usize) -> Result<(), ContractError> {
    scan(bytes, max_depth, false).map(|_| ())
}

/// JSON.parse selects the last root schemaVersion before an executable pack's
/// strict parser runs. Inspect raw UTF-16 units without prematurely rejecting
/// another property's surrogate escapes or duplicate keys.
pub(crate) fn legacy_pack_profile(bytes: &[u8], max_depth: usize) -> Result<bool, ContractError> {
    scan(bytes, max_depth, true)
}

fn scan(bytes: &[u8], max_depth: usize, legacy: bool) -> Result<bool, ContractError> {
    let mut syntax = serde_json::Deserializer::from_slice(bytes);
    syntax.disable_recursion_limit();
    let raw: &serde_json::value::RawValue = Deserialize::deserialize(&mut syntax)?;
    syntax.end()?;
    let mut scanner = Scanner {
        text: raw.get(),
        offset: 0,
        max_depth,
        legacy,
        executable: false,
    };
    scanner.value(0)?;
    Ok(scanner.executable)
}

// Render legacy file-loader syntax findings from the existing grammar checker.
// These templates are exercised by frozen Node 22 observations; unfamiliar
// causes retain an explicit native finding, not a fabricated matching message.
pub(crate) fn legacy_syntax_message(text: &str, error: &serde_json::Error) -> String {
    let raw = error.to_string();
    let suffix = format!(" at line {} column {}", error.line(), error.column());
    let cause = raw.strip_suffix(&suffix).unwrap_or(&raw);
    if cause == "EOF while parsing a value" {
        return "Unexpected end of JSON input".into();
    }
    if text == "undefined" {
        return "\"undefined\" is not valid JSON".into();
    }
    if text.starts_with('\u{feff}') {
        let head = text.chars().take(10).collect::<String>();
        return format!("Unexpected token '\u{feff}', \"{head}\"... is not valid JSON");
    }
    let mut offset = if error.is_eof() {
        text.len()
    } else {
        text.split_inclusive('\n')
            .take(error.line().saturating_sub(1))
            .map(str::len)
            .sum::<usize>()
            + error.column().saturating_sub(1)
    }
    .min(text.len());
    while !text.is_char_boundary(offset) {
        offset -= 1;
    }
    let prefix = &text[..offset];
    let position = prefix.encode_utf16().count();
    let line = prefix.bytes().filter(|byte| *byte == b'\n').count() + 1;
    let column = prefix
        .rsplit('\n')
        .next()
        .unwrap_or("")
        .encode_utf16()
        .count()
        + 1;
    let message = match cause {
        "key must be a string" | "expected `\"`" if prefix.trim_end().ends_with('{') => {
            "Expected property name or '}'"
        }
        "key must be a string" | "expected `\"`" => "Expected double-quoted property name",
        "expected `:`" => "Expected ':' after property name",
        "expected `,` or `}`" => "Expected ',' or '}' after property value",
        "expected `,` or `]`" => "Expected ',' or ']' after array element",
        "trailing characters" => "Unexpected non-whitespace character after JSON",
        "EOF while parsing an object" if text.trim_end().ends_with('{') => {
            "Expected property name or '}'"
        }
        "EOF while parsing an object" if text.trim_end().ends_with(',') => {
            "Expected double-quoted property name"
        }
        _ => return format!("Unmapped legacy JSON syntax diagnostic: {raw}"),
    };
    let location = if cause == "trailing characters" {
        ""
    } else {
        " in JSON"
    };
    format!("{message}{location} at position {position} (line {line} column {column})")
}

struct Scanner<'a> {
    text: &'a str,
    offset: usize,
    max_depth: usize,
    legacy: bool,
    executable: bool,
}
impl Scanner<'_> {
    fn whitespace(&mut self) {
        while self
            .text
            .as_bytes()
            .get(self.offset)
            .is_some_and(|b| matches!(b, b' ' | b'\t' | b'\r' | b'\n'))
        {
            self.offset += 1;
        }
    }
    fn string(&mut self) -> &str {
        let start = self.offset;
        self.offset += 1;
        loop {
            match self.text.as_bytes()[self.offset] {
                b'\\' => self.offset += 2,
                b'"' => {
                    self.offset += 1;
                    return &self.text[start..self.offset];
                }
                _ => self.offset += 1,
            }
        }
    }
    fn value(&mut self, depth: usize) -> Result<(), ContractError> {
        if depth > self.max_depth {
            return Err(ContractError::DepthLimit {
                max_depth: self.max_depth,
            });
        }
        self.whitespace();
        match self.text.as_bytes()[self.offset] {
            b'"' => {
                self.string();
            }
            b'{' => {
                self.offset += 1;
                self.whitespace();
                let mut keys = HashSet::new();
                while self.text.as_bytes()[self.offset] != b'}' {
                    let key = decode_key(self.string());
                    if !self.legacy && keys.contains(&key) {
                        return Err(ContractError::DuplicateKey {
                            key_json: display_key(&key),
                        });
                    }
                    if !self.legacy {
                        keys.insert(key.clone());
                    }
                    self.whitespace();
                    self.offset += 1; // colon, already proved by grammar validation
                    self.whitespace();
                    let start = self.offset;
                    self.value(depth + 1)?;
                    if self.legacy
                        && depth == 0
                        && key == "schemaVersion".encode_utf16().collect::<Vec<_>>()
                    {
                        let raw = &self.text[start..self.offset];
                        self.executable = raw.starts_with('"')
                            && decode_key(raw) == "2.0.0".encode_utf16().collect::<Vec<_>>();
                    }
                    self.whitespace();
                    if self.text.as_bytes()[self.offset] != b',' {
                        break;
                    }
                    self.offset += 1;
                    self.whitespace();
                }
                self.offset += 1;
            }
            b'[' => {
                self.offset += 1;
                self.whitespace();
                while self.text.as_bytes()[self.offset] != b']' {
                    self.value(depth + 1)?;
                    self.whitespace();
                    if self.text.as_bytes()[self.offset] != b',' {
                        break;
                    }
                    self.offset += 1;
                }
                self.offset += 1;
            }
            _ => {
                while self.text.as_bytes().get(self.offset).is_some_and(|b| {
                    !matches!(b, b' ' | b'\t' | b'\r' | b'\n' | b',' | b'}' | b']')
                }) {
                    self.offset += 1;
                }
            }
        }
        Ok(())
    }
}

/// A decoded JSON key can contain unpaired UTF-16 escapes. Preserve their units
/// until duplicate detection; scalar Unicode validation happens afterwards.
pub(crate) fn decode_key(raw: &str) -> Vec<u16> {
    let mut units = Vec::new();
    let mut chars = raw[1..raw.len() - 1].chars();
    while let Some(ch) = chars.next() {
        if ch != '\\' {
            units.extend(ch.encode_utf16(&mut [0; 2]).iter().copied());
            continue;
        }
        match chars.next().expect("grammar-checked escape") {
            'u' => {
                let mut unit = 0u16;
                for _ in 0..4 {
                    unit = unit * 16
                        + chars
                            .next()
                            .expect("grammar-checked hex")
                            .to_digit(16)
                            .expect("hex") as u16;
                }
                units.push(unit);
            }
            'b' => units.push(8),
            'f' => units.push(12),
            'n' => units.push(10),
            'r' => units.push(13),
            't' => units.push(9),
            ch => units.push(ch as u16),
        }
    }
    units
}

pub(crate) fn display_key(units: &[u16]) -> String {
    let mut output = String::from("\"");
    let mut index = 0;
    while index < units.len() {
        let unit = units[index];
        index += 1;
        if (0xd800..=0xdbff).contains(&unit)
            && units
                .get(index)
                .is_some_and(|next| (0xdc00..=0xdfff).contains(next))
        {
            let low = units[index];
            index += 1;
            let ch =
                char::from_u32(0x10000 + (((unit as u32 - 0xd800) << 10) | (low as u32 - 0xdc00)))
                    .expect("surrogate pair");
            output.push(ch);
        } else if (0xd800..=0xdfff).contains(&unit) {
            write!(&mut output, "\\u{unit:04x}").expect("string writer");
        } else {
            let encoded = serde_json::to_string(
                &char::from_u32(unit as u32)
                    .expect("scalar unit")
                    .to_string(),
            )
            .expect("string");
            output.push_str(&encoded[1..encoded.len() - 1]);
        }
    }
    output.push('"');
    output
}
