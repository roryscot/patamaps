use crate::{EntityProfile, Error, FormatVersion, Result, SssomDocument, refuse};
use patamaps_contracts::{JsonLimits, JsonObject};
use serde_json::{Map, Number, Value};
use yaml_rust2::{
    Yaml,
    parser::{Event, Parser},
    scanner::TScalarStyle,
};

pub(crate) fn text(bytes: &[u8], limits: JsonLimits) -> Result<&str> {
    if bytes.len() > limits.max_bytes {
        return Err(Error::new(
            "SSSOM_SIZE_LIMIT",
            format!("Source exceeds {} bytes", limits.max_bytes),
        ));
    }
    let source =
        std::str::from_utf8(bytes).map_err(|_| Error::new("SSSOM_UTF8", "Invalid UTF-8"))?;
    if source.starts_with('\u{feff}') {
        return refuse("SSSOM_BOM", "Byte order marks are unsupported");
    }
    Ok(source)
}
enum Frame {
    Array(Vec<Value>),
    Object(Map<String, Value>, Option<String>),
}
fn scalar(value: &str, style: TScalarStyle) -> Result<Value> {
    if style != TScalarStyle::Plain {
        return Ok(Value::String(value.into()));
    }
    if matches!(value, "Null" | "NULL") {
        return Ok(Value::Null);
    }
    Ok(match Yaml::from_str(value) {
        Yaml::Null => Value::Null,
        Yaml::Boolean(v) => Value::Bool(v),
        Yaml::Integer(v) => Value::Number(Number::from_f64(v as f64).expect("finite integer")),
        Yaml::Real(v) => Value::Number(
            Number::from_f64(
                v.parse()
                    .map_err(|_| Error::new("SSSOM_METADATA_YAML", "Unsupported numeric scalar"))?,
            )
            .ok_or_else(|| Error::new("SSSOM_METADATA_YAML", "Nonfinite scalar"))?,
        ),
        _ => Value::String(value.into()),
    })
}
fn attach(stack: &mut [Frame], root: &mut Option<Value>, value: Value) -> Result<()> {
    match stack.last_mut() {
        Some(Frame::Array(values)) => values.push(value),
        Some(Frame::Object(values, pending)) => {
            if let Some(key) = pending.take() {
                if values.insert(key, value).is_some() {
                    return refuse("SSSOM_METADATA_YAML", "Duplicate decoded YAML key");
                }
            } else {
                let Value::String(key) = value else {
                    return refuse("SSSOM_METADATA_YAML", "Metadata requires string keys");
                };
                if values.contains_key(&key) {
                    return refuse("SSSOM_METADATA_YAML", "Duplicate decoded YAML key");
                }
                *pending = Some(key);
            }
        }
        None => {
            if root.replace(value).is_some() {
                return refuse("SSSOM_METADATA_YAML", "Multiple root values");
            }
        }
    }
    Ok(())
}
pub(crate) fn metadata(source: &str, limits: JsonLimits) -> Result<JsonObject> {
    if source.lines().any(|line| line.starts_with('%')) {
        return refuse("SSSOM_FORBIDDEN_YAML", "Directives are unsupported");
    }
    let mut parser = Parser::new_from_str(source);
    let mut stack = Vec::new();
    let mut root = None;
    let mut count = 0usize;
    let mut documents = 0;
    loop {
        let (event, _) = parser
            .next_token()
            .map_err(|_| Error::new("SSSOM_METADATA_YAML", "Malformed YAML 1.2"))?;
        count += 1;
        if count > limits.max_values || stack.len() > limits.max_depth {
            return refuse("SSSOM_METADATA_LIMIT", "Metadata exceeds structural limits");
        }
        match event {
            Event::StreamEnd => break,
            Event::DocumentStart => {
                documents += 1;
                if documents > 1 {
                    return refuse("SSSOM_METADATA_YAML", "Multiple YAML documents");
                }
            }
            Event::Alias(_) => return refuse("SSSOM_FORBIDDEN_YAML", "Aliases are unsupported"),
            Event::Scalar(v, style, anchor, tag) => {
                if anchor != 0 || tag.is_some() {
                    return refuse("SSSOM_FORBIDDEN_YAML", "Anchors and tags are unsupported");
                }
                attach(&mut stack, &mut root, scalar(&v, style)?)?;
            }
            Event::SequenceStart(anchor, ref tag) | Event::MappingStart(anchor, ref tag) => {
                if anchor != 0 || tag.is_some() {
                    return refuse("SSSOM_FORBIDDEN_YAML", "Anchors and tags are unsupported");
                }
                if matches!(stack.last(), Some(Frame::Object(_, None))) {
                    return refuse("SSSOM_METADATA_YAML", "Compound keys are unsupported");
                }
                stack.push(if matches!(event, Event::SequenceStart(..)) {
                    Frame::Array(Vec::new())
                } else {
                    Frame::Object(Map::new(), None)
                });
            }
            Event::SequenceEnd | Event::MappingEnd => {
                let frame = stack
                    .pop()
                    .ok_or_else(|| Error::new("SSSOM_METADATA_YAML", "Unbalanced YAML"))?;
                let value = match frame {
                    Frame::Array(v) => Value::Array(v),
                    Frame::Object(v, None) => Value::Object(v),
                    Frame::Object(_, Some(_)) => {
                        return refuse("SSSOM_METADATA_YAML", "Missing YAML value");
                    }
                };
                attach(&mut stack, &mut root, value)?;
            }
            _ => (),
        }
    }
    let Some(Value::Object(map)) = root else {
        return refuse("SSSOM_METADATA_YAML", "Metadata must be a mapping");
    };
    Ok(map.into_iter().collect())
}

pub(crate) fn tsv(source: &str) -> Result<Vec<Vec<String>>> {
    let mut records = Vec::new();
    let mut row = Vec::new();
    let mut field = String::new();
    let mut quoted = false;
    let mut ended = false;
    let mut started = false;
    let mut chars = source.chars().peekable();
    while let Some(c) = chars.next() {
        if quoted {
            if c == '"' {
                if chars.peek() == Some(&'"') {
                    field.push('"');
                    chars.next();
                } else {
                    quoted = false;
                    ended = true;
                }
            } else {
                field.push(c);
            }
        } else if c == '\t' || c == '\n' || c == '\r' {
            row.push(std::mem::take(&mut field));
            ended = false;
            started = false;
            if row.len() > 256 {
                return refuse("SSSOM_COLUMN_LIMIT", "More than 256 columns");
            }
            if c != '\t' {
                records.push(std::mem::take(&mut row));
                if records.len() > 50_001 {
                    return refuse("SSSOM_ROW_LIMIT", "More than 50000 records");
                }
                if c == '\r' && chars.peek() == Some(&'\n') {
                    chars.next();
                }
            }
        } else if c == '"' && !started && !ended {
            quoted = true;
            started = true;
        } else {
            if ended || c == '"' {
                return refuse("SSSOM_TSV_QUOTING", "Invalid quote position");
            }
            field.push(c);
            started = true;
        }
    }
    if quoted {
        return refuse("SSSOM_TSV_QUOTING", "Unclosed quoted field");
    }
    if !row.is_empty() || started || ended {
        row.push(field);
        if row.len() > 256 {
            return refuse("SSSOM_COLUMN_LIMIT", "More than 256 columns");
        }
        records.push(row);
    }
    if records.len() > 50_001 {
        return refuse("SSSOM_ROW_LIMIT", "More than 50000 records");
    }
    Ok(records)
}
pub(crate) fn decode(
    input: &[u8],
    external: Option<&[u8]>,
    limits: JsonLimits,
) -> Result<SssomDocument> {
    let mut source = text(input, limits)?;
    let yaml = if let Some(external) = external {
        if source.starts_with('#') {
            return refuse(
                "SSSOM_METADATA_MODE",
                "External metadata cannot be combined with embedded metadata",
            );
        }
        text(external, limits)?.to_owned()
    } else {
        let mut lines = Vec::new();
        while source.starts_with('#') {
            let end = source
                .find(['\r', '\n'])
                .ok_or_else(|| Error::new("SSSOM_TSV_HEADER", "Missing TSV block"))?;
            lines.push(&source[1..end]);
            let separator = if source[end..].starts_with("\r\n") {
                2
            } else {
                1
            };
            source = &source[end + separator..];
        }
        let Some(first) = lines.first() else {
            return refuse("SSSOM_METADATA", "No embedded metadata");
        };
        let spaces = first.bytes().take_while(|c| *c == b' ').count();
        if lines
            .iter()
            .any(|line| !line.starts_with(&" ".repeat(spaces)))
        {
            return refuse("SSSOM_METADATA_INDENT", "Inconsistent comment indentation");
        }
        lines
            .iter()
            .map(|line| &line[spaces..])
            .collect::<Vec<_>>()
            .join("\n")
    };
    let mut rows = tsv(source)?.into_iter();
    let columns = rows
        .next()
        .ok_or_else(|| Error::new("SSSOM_TSV_HEADER", "Missing TSV header"))?;
    Ok(SssomDocument {
        schema_version: FormatVersion::Sssom1,
        profile: EntityProfile::Entity1,
        metadata: metadata(&yaml, limits)?,
        columns,
        rows: rows.collect(),
    })
}
