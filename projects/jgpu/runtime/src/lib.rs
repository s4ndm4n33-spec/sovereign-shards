// Copyright (c) 2026 Mike McCollum
//
// Licensed under the Sovereign Shards License.
// See LICENSE.md for details.

pub mod graph;

use backend::{BackendError, BackendHandle, BackendKind, BackendRegistry};
use crossbeam_channel::{Receiver, Sender, unbounded};
use std::fmt;
use std::thread;
use tensor::Tensor;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RuntimeError {
    Backend(BackendError),
    WorkerStopped,
}

impl fmt::Display for RuntimeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            RuntimeError::Backend(err) => write!(f, "{err}"),
            RuntimeError::WorkerStopped => write!(f, "runtime worker stopped"),
        }
    }
}

impl std::error::Error for RuntimeError {}

impl From<BackendError> for RuntimeError {
    fn from(value: BackendError) -> Self {
        Self::Backend(value)
    }
}

#[derive(Debug)]
pub enum Command {
    MatMul {
        backend: BackendKind,
        a: Tensor,
        b: Tensor,
        resp: Sender<Result<Tensor, RuntimeError>>,
    },
    Add {
        backend: BackendKind,
        a: Tensor,
        b: Tensor,
        resp: Sender<Result<Tensor, RuntimeError>>,
    },
    Shutdown,
}

pub struct Runtime {
    tx: Sender<Command>,
    worker: Option<thread::JoinHandle<()>>,
    default_backend: BackendKind,
}

impl Runtime {
    pub fn start() -> Self {
        Self::start_with_registry(BackendRegistry::with_cpu(), BackendKind::Cpu)
    }

    pub fn start_with_registry(registry: BackendRegistry, default_backend: BackendKind) -> Self {
        let (tx, rx) = unbounded::<Command>();
        let worker = thread::spawn(move || executor_loop(rx, registry));
        Self {
            tx,
            worker: Some(worker),
            default_backend,
        }
    }

    pub fn submit_matmul(&self, a: Tensor, b: Tensor) -> Receiver<Result<Tensor, RuntimeError>> {
        self.submit_matmul_on(self.default_backend, a, b)
    }

    pub fn submit_matmul_on(
        &self,
        backend: BackendKind,
        a: Tensor,
        b: Tensor,
    ) -> Receiver<Result<Tensor, RuntimeError>> {
        let (resp_tx, resp_rx) = unbounded();
        if self
            .tx
            .send(Command::MatMul {
                backend,
                a,
                b,
                resp: resp_tx.clone(),
            })
            .is_err()
        {
            let _ = resp_tx.send(Err(RuntimeError::WorkerStopped));
        }
        resp_rx
    }

    pub fn submit_add(&self, a: Tensor, b: Tensor) -> Receiver<Result<Tensor, RuntimeError>> {
        self.submit_add_on(self.default_backend, a, b)
    }

    pub fn submit_add_on(
        &self,
        backend: BackendKind,
        a: Tensor,
        b: Tensor,
    ) -> Receiver<Result<Tensor, RuntimeError>> {
        let (resp_tx, resp_rx) = unbounded();
        if self
            .tx
            .send(Command::Add {
                backend,
                a,
                b,
                resp: resp_tx.clone(),
            })
            .is_err()
        {
            let _ = resp_tx.send(Err(RuntimeError::WorkerStopped));
        }
        resp_rx
    }
}

impl Drop for Runtime {
    fn drop(&mut self) {
        let _ = self.tx.send(Command::Shutdown);
        if let Some(h) = self.worker.take() {
            let _ = h.join();
        }
    }
}

fn executor_loop(rx: Receiver<Command>, registry: BackendRegistry) {
    while let Ok(cmd) = rx.recv() {
        match cmd {
            Command::MatMul {
                backend,
                a,
                b,
                resp,
            } => {
                let result =
                    execute_with_backend(&registry, backend, |backend| backend.matmul(&a, &b));
                let _ = resp.send(result);
            }
            Command::Add {
                backend,
                a,
                b,
                resp,
            } => {
                let result =
                    execute_with_backend(&registry, backend, |backend| backend.add(&a, &b));
                let _ = resp.send(result);
            }
            Command::Shutdown => break,
        }
    }
}

fn execute_with_backend(
    registry: &BackendRegistry,
    kind: BackendKind,
    op: impl FnOnce(BackendHandle) -> Result<Tensor, BackendError>,
) -> Result<Tensor, RuntimeError> {
    let backend = registry.get(kind)?;
    Ok(op(backend)?)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn async_matmul_executes() {
        let rt = Runtime::start();
        let a = Tensor::new(vec![2, 2], tensor::DType::F32, vec![1.0, 2.0, 3.0, 4.0]);
        let b = Tensor::new(vec![2, 2], tensor::DType::F32, vec![5.0, 6.0, 7.0, 8.0]);
        let rx = rt.submit_matmul(a, b);
        let out = rx.recv().expect("result").expect("matmul ok");
        assert_eq!(out.data, vec![19.0, 22.0, 43.0, 50.0]);
    }

    #[test]
    fn unsupported_backend_is_reported() {
        let rt = Runtime::start();
        let rx = rt.submit_add_on(BackendKind::Cuda, Tensor::ones(&[1]), Tensor::ones(&[1]));
        let err = rx.recv().expect("result").unwrap_err();
        assert_eq!(
            err,
            RuntimeError::Backend(BackendError::UnsupportedBackend(BackendKind::Cuda))
        );
    }
}
