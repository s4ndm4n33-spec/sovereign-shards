use criterion::{criterion_group, criterion_main, Criterion};
use kernels::{matmul, matmul_parallel};
use tensor::Tensor;

fn bench_matmul(c: &mut Criterion) {
    let a = Tensor::random(&[128, 128], -1.0, 1.0);
    let b = Tensor::random(&[128, 128], -1.0, 1.0);

    c.bench_function("matmul_naive_128", |ben| ben.iter(|| matmul(&a, &b)));
    c.bench_function("matmul_parallel_128", |ben| ben.iter(|| matmul_parallel(&a, &b)));
}

criterion_group!(benches, bench_matmul);
criterion_main!(benches);
