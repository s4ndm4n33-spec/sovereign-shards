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
}
