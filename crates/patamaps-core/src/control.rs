use crate::{CheckError, Issue};
use std::{
    cell::Cell,
    sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
    },
    time::{Duration, Instant},
};

/// Host-only cancellation. This is not portable semantic input or authority.
#[derive(Debug, Clone, Default)]
pub struct CancellationToken(Arc<AtomicBool>);
impl CancellationToken {
    pub fn cancel(&self) {
        self.0.store(true, Ordering::Relaxed);
    }
    pub fn cancelled(&self) -> bool {
        self.0.load(Ordering::Relaxed)
    }
}
#[derive(Debug)]
pub struct WorkControl {
    token: CancellationToken,
    deadline: Instant,
    maximum: u64,
    used: Cell<u64>,
}
impl WorkControl {
    pub fn new(token: CancellationToken, elapsed: Duration, maximum: u64) -> Self {
        Self {
            token,
            deadline: Instant::now()
                .checked_add(elapsed)
                .unwrap_or_else(Instant::now),
            maximum,
            used: Cell::new(0),
        }
    }
    pub fn used(&self) -> u64 {
        self.used.get()
    }
    pub fn poll(&self) -> Result<(), CheckError> {
        let code = if self.token.cancelled() {
            Some("WORK_CANCELLED")
        } else if Instant::now() >= self.deadline {
            Some("WORK_ELAPSED_LIMIT")
        } else if self.used.get() >= self.maximum {
            Some("WORK_UNIT_LIMIT")
        } else {
            None
        };
        if let Some(code) = code {
            return Err(CheckError(vec![Issue::error(
                code,
                "Inspection work stopped before exhausting the declared space",
                "inspection",
            )]));
        }
        self.used.set(self.used.get() + 1);
        Ok(())
    }
}
#[inline]
pub(crate) fn poll(control: Option<&WorkControl>) -> Result<(), CheckError> {
    if let Some(c) = control {
        c.poll()?;
    }
    Ok(())
}
