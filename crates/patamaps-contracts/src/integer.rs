use serde::{Deserialize, Serialize, de::Visitor};
use std::fmt;

pub const MAX_SAFE_INTEGER: u64 = 9_007_199_254_740_991;

/// A checked, interoperable nonnegative integer; no truncating casts at ingress.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(transparent)]
pub struct SafeInteger(u64);
impl SafeInteger {
    pub fn new(value: u64) -> Option<Self> {
        (value <= MAX_SAFE_INTEGER).then_some(Self(value))
    }
    pub fn get(self) -> u64 {
        self.0
    }
    pub fn checked_add(self, other: Self) -> Option<Self> {
        Self::new(self.0.checked_add(other.0)?)
    }
}
impl<'de> Deserialize<'de> for SafeInteger {
    fn deserialize<D: serde::Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        struct Integer;
        impl<'de> Visitor<'de> for Integer {
            type Value = SafeInteger;
            fn expecting(&self, f: &mut fmt::Formatter) -> fmt::Result {
                f.write_str("a nonnegative safe integer")
            }
            fn visit_u64<E: serde::de::Error>(self, v: u64) -> Result<Self::Value, E> {
                SafeInteger::new(v).ok_or_else(|| E::custom("UNSAFE_INTEGER"))
            }
            fn visit_i64<E: serde::de::Error>(self, v: i64) -> Result<Self::Value, E> {
                u64::try_from(v)
                    .map_err(|_| E::custom("NEGATIVE_INTEGER"))
                    .and_then(|n| self.visit_u64(n))
            }
            fn visit_f64<E: serde::de::Error>(self, v: f64) -> Result<Self::Value, E> {
                if !v.is_finite() || v < 0.0 || v.fract() != 0.0 || v > MAX_SAFE_INTEGER as f64 {
                    return Err(E::custom("UNSAFE_INTEGER"));
                }
                self.visit_u64(v as u64)
            }
        }
        d.deserialize_any(Integer)
    }
}
