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

pub fn rmsnorm(input: &Tensor, gamma: &Tensor, epsilon: f32) -> Tensor {
    assert_eq!(input.shape.len(), 2, "rmsnorm expects [batch, hidden]");
    assert_eq!(gamma.shape, vec![input.shape[1]], "gamma must be [hidden]");
    let batch = input.shape[0];
    let hidden = input.shape[1];
    let mut out = Tensor::zeros(&[batch, hidden]);

    for b in 0..batch {
        let mut sq_sum = 0.0f32;
        for h in 0..hidden {
            let v = input.get(&[b, h]);
            sq_sum += v * v;
        }
        let inv_rms = 1.0 / ((sq_sum / hidden as f32) + epsilon).sqrt();
        for h in 0..hidden {
            let v = input.get(&[b, h]);
            out.set(&[b, h], v * inv_rms * gamma.get(&[h]));
        }
    }
    out
}

pub fn softmax_last_dim(input: &Tensor) -> Tensor {
    assert_eq!(input.shape.len(), 2, "softmax expects rank-2 tensor");
    let rows = input.shape[0];
    let cols = input.shape[1];
    let mut out = Tensor::zeros(&[rows, cols]);

    for r in 0..rows {
        let mut max_v = f32::NEG_INFINITY;
        for c in 0..cols {
            max_v = max_v.max(input.get(&[r, c]));
        }
        let mut sum = 0.0;
        for c in 0..cols {
            let e = (input.get(&[r, c]) - max_v).exp();
            out.set(&[r, c], e);
            sum += e;
        }
        for c in 0..cols {
            out.set(&[r, c], out.get(&[r, c]) / sum);
        }
    }
    out
}

pub fn apply_rope(q_or_k: &Tensor, theta: f32) -> Tensor {
    assert_eq!(q_or_k.shape.len(), 2, "rope expects [seq, dim]");
    let seq = q_or_k.shape[0];
    let dim = q_or_k.shape[1];
    assert_eq!(dim % 2, 0, "rope dim must be even");

    let mut out = Tensor::zeros(&[seq, dim]);
    for pos in 0..seq {
        for i in (0..dim).step_by(2) {
            let freq = 1.0 / theta.powf(i as f32 / dim as f32);
            let angle = pos as f32 * freq;
            let cos = angle.cos();
            let sin = angle.sin();
            let x0 = q_or_k.get(&[pos, i]);
            let x1 = q_or_k.get(&[pos, i + 1]);
            out.set(&[pos, i], x0 * cos - x1 * sin);
            out.set(&[pos, i + 1], x0 * sin + x1 * cos);
        }
    }
    out
}

pub fn attention(q: &Tensor, k: &Tensor, v: &Tensor) -> Tensor {
    assert_eq!(q.shape.len(), 2);
    assert_eq!(k.shape.len(), 2);
    assert_eq!(v.shape.len(), 2);
    let d = q.shape[1] as f32;

    let k_t = k.transpose2d();
    let mut scores = matmul_parallel(q, &k_t);
    for s in &mut scores.data {
        *s /= d.sqrt();
    }
    let probs = softmax_last_dim(&scores);
    matmul_parallel(&probs, v)
}

#[derive(Debug, Default)]
pub struct KvCache {
    keys: Vec<Tensor>,
    values: Vec<Tensor>,
}

impl KvCache {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn append(&mut self, key: Tensor, value: Tensor) {
        assert_eq!(key.shape, value.shape, "key/value shape mismatch");
        self.keys.push(key);
        self.values.push(value);
    }

    pub fn len(&self) -> usize {
        self.keys.len()
    }

    pub fn latest(&self) -> Option<(&Tensor, &Tensor)> {
        self.keys.last().zip(self.values.last())
    }
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

    #[test]
    fn softmax_rows_sum_to_one() {
        let t = Tensor::new(vec![2, 2], tensor::DType::F32, vec![1.0, 2.0, 3.0, 4.0]);
        let out = softmax_last_dim(&t);
        for r in 0..2 {
            let row_sum = out.get(&[r, 0]) + out.get(&[r, 1]);
            assert!((row_sum - 1.0).abs() < 1e-5);
        }
    }

    #[test]
    fn rmsnorm_scales_rows() {
        let x = Tensor::new(vec![1, 4], tensor::DType::F32, vec![1.0, 2.0, 3.0, 4.0]);
        let g = Tensor::ones(&[4]);
        let out = rmsnorm(&x, &g, 1e-5);
        assert_eq!(out.shape, x.shape);
        assert!(out.data.iter().all(|v| v.is_finite()));
    }

    #[test]
    fn rope_preserves_shape() {
        let x = Tensor::new(vec![2, 4], tensor::DType::F32, vec![1.0, 0.0, 0.5, 0.5, 1.0, 1.0, 2.0, 2.0]);
        let out = apply_rope(&x, 10_000.0);
        assert_eq!(out.shape, x.shape);
    }

    #[test]
    fn attention_produces_expected_shape() {
        let q = Tensor::new(vec![2, 2], tensor::DType::F32, vec![1.0, 0.0, 0.0, 1.0]);
        let k = Tensor::new(vec![2, 2], tensor::DType::F32, vec![1.0, 0.0, 0.0, 1.0]);
        let v = Tensor::new(vec![2, 2], tensor::DType::F32, vec![1.0, 2.0, 3.0, 4.0]);
        let out = attention(&q, &k, &v);
        assert_eq!(out.shape, vec![2, 2]);
        assert!(out.data.iter().all(|x| x.is_finite()));
    }

    #[test]
    fn kv_cache_append_and_latest() {
        let mut cache = KvCache::new();
        cache.append(Tensor::ones(&[1, 2]), Tensor::ones(&[1, 2]));
        assert_eq!(cache.len(), 1);
        let (k, v) = cache.latest().expect("latest");
        assert_eq!(k.shape, vec![1, 2]);
        assert_eq!(v.shape, vec![1, 2]);
    }
}
