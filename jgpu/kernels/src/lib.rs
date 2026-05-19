use rayon::prelude::*;
use tensor::Tensor;

pub fn matmul(a: &Tensor, b: &Tensor) -> Tensor {
    assert_eq!(a.shape.len(), 2);
    assert_eq!(b.shape.len(), 2);
    let m = a.shape[0];
    let k = a.shape[1];
    assert_eq!(k, b.shape[0]);
    let n = b.shape[1];

    let mut out = Tensor::zeros(&[m, n]);
    for i in 0..m {
        for j in 0..n {
            let mut acc = 0.0;
            for kk in 0..k {
                acc += a.get(&[i, kk]) * b.get(&[kk, j]);
            }
            out.set(&[i, j], acc);
        }
    }
    out
}

pub fn matmul_parallel(a: &Tensor, b: &Tensor) -> Tensor {
    assert_eq!(a.shape.len(), 2);
    assert_eq!(b.shape.len(), 2);
    let m = a.shape[0];
    let k = a.shape[1];
    assert_eq!(k, b.shape[0]);
    let n = b.shape[1];

    let rows: Vec<Vec<f32>> = (0..m)
        .into_par_iter()
        .map(|i| {
            let mut row = vec![0.0; n];
            for (j, slot) in row.iter_mut().enumerate().take(n) {
                let mut acc = 0.0;
                for kk in 0..k {
                    acc += a.get(&[i, kk]) * b.get(&[kk, j]);
                }
                *slot = acc;
            }
            row
        })
        .collect();

    let mut out = Tensor::zeros(&[m, n]);
    for (i, row) in rows.into_iter().enumerate() {
        for (j, v) in row.into_iter().enumerate() {
            out.set(&[i, j], v);
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn matmul_correct() {
        let a = Tensor::new(vec![2, 2], tensor::DType::F32, vec![1.0, 2.0, 3.0, 4.0]);
        let b = Tensor::new(vec![2, 2], tensor::DType::F32, vec![5.0, 6.0, 7.0, 8.0]);
        let c = matmul(&a, &b);
        assert_eq!(c.data, vec![19.0, 22.0, 43.0, 50.0]);
        let cp = matmul_parallel(&a, &b);
        assert_eq!(cp.data, c.data);
    }
}
