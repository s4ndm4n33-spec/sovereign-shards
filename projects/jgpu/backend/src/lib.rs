// Copyright (c) 2026 Mike McCollum
//
// Licensed under the Sovereign Shards License.
// See LICENSE.md for details.

use std::collections::HashMap;
use std::fmt;
use std::sync::Arc;
use std::time::{Duration, Instant};

use tensor::Tensor;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum BackendKind {
    Cpu,
    SimdCpu,
    Cuda,
    Metal,
    Vulkan,
    Rocm,
    WebGpu,
    Remote,
    Distributed,
    Mock,
}

impl BackendKind {
    pub const ALL: [BackendKind; 10] = [
        BackendKind::Cpu,
        BackendKind::SimdCpu,
        BackendKind::Cuda,
        BackendKind::Metal,
        BackendKind::Vulkan,
        BackendKind::Rocm,
        BackendKind::WebGpu,
        BackendKind::Remote,
        BackendKind::Distributed,
        BackendKind::Mock,
    ];
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum BackendError {
    UnsupportedBackend(BackendKind),
    UnsupportedOp {
        backend: BackendKind,
        op: &'static str,
    },
    InvalidInput(String),
}

impl fmt::Display for BackendError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            BackendError::UnsupportedBackend(kind) => write!(f, "unsupported backend: {kind:?}"),
            BackendError::UnsupportedOp { backend, op } => {
                write!(f, "backend {backend:?} does not support op {op}")
            }
            BackendError::InvalidInput(msg) => write!(f, "invalid backend input: {msg}"),
        }
    }
}

impl std::error::Error for BackendError {}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct BackendCapabilities {
    pub matmul: bool,
    pub add: bool,
    pub async_launch: bool,
    pub graph_execution: bool,
    pub distributed: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct BackendDescriptor {
    pub kind: BackendKind,
    pub name: &'static str,
    pub version: &'static str,
    pub capabilities: BackendCapabilities,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProfileEvent {
    pub backend: BackendKind,
    pub op: &'static str,
    pub elapsed: Duration,
    pub elements: usize,
}

pub trait ExecutionBackend: Send + Sync {
    fn descriptor(&self) -> BackendDescriptor;

    fn matmul(&self, a: &Tensor, b: &Tensor) -> Result<Tensor, BackendError> {
        let _ = (a, b);
        Err(BackendError::UnsupportedOp {
            backend: self.descriptor().kind,
            op: "matmul",
        })
    }

    fn add(&self, a: &Tensor, b: &Tensor) -> Result<Tensor, BackendError> {
        let _ = (a, b);
        Err(BackendError::UnsupportedOp {
            backend: self.descriptor().kind,
            op: "add",
        })
    }
}

pub type BackendHandle = Arc<dyn ExecutionBackend>;

#[derive(Default)]
pub struct BackendRegistry {
    backends: HashMap<BackendKind, BackendHandle>,
}

impl BackendRegistry {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn with_cpu() -> Self {
        let mut registry = Self::new();
        registry.register(Arc::new(CpuBackend::default()));
        registry
    }

    pub fn register(&mut self, backend: BackendHandle) {
        self.backends.insert(backend.descriptor().kind, backend);
    }

    pub fn get(&self, kind: BackendKind) -> Result<BackendHandle, BackendError> {
        self.backends
            .get(&kind)
            .cloned()
            .ok_or(BackendError::UnsupportedBackend(kind))
    }

    pub fn registered_kinds(&self) -> Vec<BackendKind> {
        let mut kinds: Vec<_> = self.backends.keys().copied().collect();
        kinds.sort_by_key(|kind| {
            BackendKind::ALL
                .iter()
                .position(|candidate| candidate == kind)
        });
        kinds
    }

    pub fn supported_slots(&self) -> &'static [BackendKind; 10] {
        &BackendKind::ALL
    }
}

#[derive(Debug, Default)]
pub struct CpuBackend;

impl ExecutionBackend for CpuBackend {
    fn descriptor(&self) -> BackendDescriptor {
        BackendDescriptor {
            kind: BackendKind::Cpu,
            name: "cpu",
            version: env!("CARGO_PKG_VERSION"),
            capabilities: BackendCapabilities {
                matmul: true,
                add: true,
                async_launch: true,
                graph_execution: true,
                distributed: false,
            },
        }
    }

    fn matmul(&self, a: &Tensor, b: &Tensor) -> Result<Tensor, BackendError> {
        let start = Instant::now();
        let out = kernels::matmul(a, b);
        log_profile(ProfileEvent {
            backend: BackendKind::Cpu,
            op: "matmul",
            elapsed: start.elapsed(),
            elements: out.data.len(),
        });
        Ok(out)
    }

    fn add(&self, a: &Tensor, b: &Tensor) -> Result<Tensor, BackendError> {
        if a.shape != b.shape {
            return Err(BackendError::InvalidInput(
                "shape mismatch for add".to_string(),
            ));
        }
        let start = Instant::now();
        let mut out = Tensor::zeros(&a.shape);
        for (idx, (va, vb)) in a.data.iter().zip(&b.data).enumerate() {
            out.data[idx] = va + vb;
        }
        log_profile(ProfileEvent {
            backend: BackendKind::Cpu,
            op: "add",
            elapsed: start.elapsed(),
            elements: out.data.len(),
        });
        Ok(out)
    }
}

fn log_profile(event: ProfileEvent) {
    eprintln!(
        "jgpu_profile backend={:?} op={} elements={} elapsed_us={}",
        event.backend,
        event.op,
        event.elements,
        event.elapsed.as_micros()
    );
}

pub struct BackendInfo {
    pub name: &'static str,
    pub version: &'static str,
}

pub fn jgpu_backend_info() -> BackendInfo {
    BackendInfo {
        name: "jgpu",
        version: env!("CARGO_PKG_VERSION"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn backend_identity_exposed() {
        let info = jgpu_backend_info();
        assert_eq!(info.name, "jgpu");
        assert!(!info.version.is_empty());
    }

    #[test]
    fn registry_exposes_ten_backend_slots_with_cpu_registered() {
        let registry = BackendRegistry::with_cpu();
        assert_eq!(registry.supported_slots().len(), 10);
        assert_eq!(registry.registered_kinds(), vec![BackendKind::Cpu]);
        assert!(registry.get(BackendKind::Cpu).is_ok());
        let err = match registry.get(BackendKind::Cuda) {
            Ok(_) => panic!("cuda should not be registered"),
            Err(err) => err,
        };
        assert_eq!(err, BackendError::UnsupportedBackend(BackendKind::Cuda));
    }

    #[test]
    fn cpu_backend_executes_core_ops() {
        let backend = CpuBackend;
        let a = Tensor::new(vec![2, 2], tensor::DType::F32, vec![1.0, 2.0, 3.0, 4.0]);
        let b = Tensor::new(vec![2, 2], tensor::DType::F32, vec![5.0, 6.0, 7.0, 8.0]);
        let mm = backend.matmul(&a, &b).expect("matmul");
        assert_eq!(mm.data, vec![19.0, 22.0, 43.0, 50.0]);
        let sum = backend.add(&mm, &Tensor::ones(&[2, 2])).expect("add");
        assert_eq!(sum.data, vec![20.0, 23.0, 44.0, 51.0]);
    }
}
