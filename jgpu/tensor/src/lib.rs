use rand::Rng;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DType {
    F32,
    F16,
    I8,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Tensor {
    pub shape: Vec<usize>,
    pub strides: Vec<usize>,
    pub dtype: DType,
    pub data: Vec<f32>,
}

impl Tensor {
    pub fn zeros(shape: &[usize]) -> Self {
        let len = shape.iter().product();
        Self::new(shape.to_vec(), DType::F32, vec![0.0; len])
    }

    pub fn ones(shape: &[usize]) -> Self {
        let len = shape.iter().product();
        Self::new(shape.to_vec(), DType::F32, vec![1.0; len])
    }

    pub fn random(shape: &[usize], low: f32, high: f32) -> Self {
        let len = shape.iter().product();
        let mut rng = rand::rng();
        let mut data = Vec::with_capacity(len);
        for _ in 0..len {
            data.push(rng.random_range(low..high));
        }
        Self::new(shape.to_vec(), DType::F32, data)
    }

    pub fn new(shape: Vec<usize>, dtype: DType, data: Vec<f32>) -> Self {
        let expected: usize = shape.iter().product();
        assert_eq!(expected, data.len(), "data length must match shape product");
        let strides = compute_strides(&shape);
        Self { shape, strides, dtype, data }
    }

    pub fn reshape(&self, shape: &[usize]) -> Self {
        let expected: usize = shape.iter().product();
        assert_eq!(expected, self.data.len(), "reshape must preserve element count");
        Self::new(shape.to_vec(), self.dtype, self.data.clone())
    }

    pub fn flatten(&self) -> Self {
        self.reshape(&[self.data.len()])
    }

    pub fn transpose2d(&self) -> Self {
        assert_eq!(self.shape.len(), 2, "transpose2d requires a rank-2 tensor");
        let rows = self.shape[0];
        let cols = self.shape[1];
        let mut out = Tensor::zeros(&[cols, rows]);
        for r in 0..rows {
            for c in 0..cols {
                let v = self.get(&[r, c]);
                out.set(&[c, r], v);
            }
        }
        out
    }

    pub fn get(&self, idx: &[usize]) -> f32 {
        let flat = self.flat_index(idx);
        self.data[flat]
    }

    pub fn set(&mut self, idx: &[usize], value: f32) {
        let flat = self.flat_index(idx);
        self.data[flat] = value;
    }

    fn flat_index(&self, idx: &[usize]) -> usize {
        assert_eq!(idx.len(), self.shape.len(), "index rank mismatch");
        let mut flat = 0;
        for (i, &v) in idx.iter().enumerate() {
            assert!(v < self.shape[i], "index out of bounds at dim {i}");
            flat += v * self.strides[i];
        }
        flat
    }
}

fn compute_strides(shape: &[usize]) -> Vec<usize> {
    if shape.is_empty() { return vec![]; }
    let mut strides = vec![0; shape.len()];
    let mut stride = 1;
    for i in (0..shape.len()).rev() {
        strides[i] = stride;
        stride *= shape[i];
    }
    strides
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn zeros_and_ones_work() {
        let z = Tensor::zeros(&[2, 3]);
        assert!(z.data.iter().all(|v| *v == 0.0));
        let o = Tensor::ones(&[2, 3]);
        assert!(o.data.iter().all(|v| *v == 1.0));
    }

    #[test]
    fn indexing_row_major() {
        let t = Tensor::new(vec![2, 3], DType::F32, vec![1., 2., 3., 4., 5., 6.]);
        assert_eq!(t.get(&[0, 0]), 1.0);
        assert_eq!(t.get(&[1, 2]), 6.0);
    }

    #[test]
    fn transpose_works() {
        let t = Tensor::new(vec![2, 3], DType::F32, vec![1., 2., 3., 4., 5., 6.]);
        let tt = t.transpose2d();
        assert_eq!(tt.shape, vec![3, 2]);
        assert_eq!(tt.data, vec![1., 4., 2., 5., 3., 6.]);
    }
}
