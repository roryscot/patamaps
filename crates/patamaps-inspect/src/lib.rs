//! Inspection proposes data; it has no source-writing or activation capability.
#![forbid(unsafe_code)]
mod explanation;
mod repair;
pub use explanation::*;
pub use repair::*;
