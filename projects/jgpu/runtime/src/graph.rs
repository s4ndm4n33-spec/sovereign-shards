// Copyright (c) 2026 Mike McCollum
//
// Licensed under the Sovereign Shards License.
// See LICENSE.md for details.

use std::collections::{HashMap, VecDeque};

use backend::{BackendKind, BackendRegistry};
use tensor::Tensor;

use crate::RuntimeError;

#[derive(Debug, Clone)]
pub enum Op {
    Input(Tensor),
    MatMul,
    Add,
}

#[derive(Debug, Clone)]
pub struct Node {
    pub id: usize,
    pub op: Op,
    pub inputs: Vec<usize>,
    pub backend: Option<BackendKind>,
}

#[derive(Debug, Default)]
pub struct Graph {
    nodes: Vec<Node>,
}

impl Graph {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn add_node(&mut self, op: Op, inputs: Vec<usize>) -> usize {
        self.add_node_on(None, op, inputs)
    }

    pub fn add_node_on(
        &mut self,
        backend: Option<BackendKind>,
        op: Op,
        inputs: Vec<usize>,
    ) -> usize {
        let id = self.nodes.len();
        self.nodes.push(Node {
            id,
            op,
            inputs,
            backend,
        });
        id
    }

    pub fn execute(&self) -> Result<HashMap<usize, Tensor>, RuntimeError> {
        let registry = BackendRegistry::with_cpu();
        self.execute_with_registry(&registry, BackendKind::Cpu)
    }

    pub fn execute_with_registry(
        &self,
        registry: &BackendRegistry,
        default_backend: BackendKind,
    ) -> Result<HashMap<usize, Tensor>, RuntimeError> {
        let order = self.topological_order()?;
        let mut results: HashMap<usize, Tensor> = HashMap::new();

        for id in order {
            let node = &self.nodes[id];
            let out = match &node.op {
                Op::Input(t) => t.clone(),
                Op::MatMul => {
                    let (a, b) = self.two_inputs(node, &results, "MatMul")?;
                    registry
                        .get(node.backend.unwrap_or(default_backend))?
                        .matmul(a, b)?
                }
                Op::Add => {
                    let (a, b) = self.two_inputs(node, &results, "Add")?;
                    registry
                        .get(node.backend.unwrap_or(default_backend))?
                        .add(a, b)?
                }
            };
            results.insert(id, out);
        }

        Ok(results)
    }

    pub fn topological_order(&self) -> Result<Vec<usize>, RuntimeError> {
        let n = self.nodes.len();
        let mut indegree = vec![0usize; n];
        let mut edges: Vec<Vec<usize>> = vec![Vec::new(); n];

        for node in &self.nodes {
            for &input in &node.inputs {
                if input >= n {
                    return Err(RuntimeError::Backend(backend::BackendError::InvalidInput(
                        format!("node {} references unknown input {}", node.id, input),
                    )));
                }
                indegree[node.id] += 1;
                edges[input].push(node.id);
            }
        }

        let mut q: VecDeque<usize> = (0..n).filter(|&i| indegree[i] == 0).collect();
        let mut order = Vec::with_capacity(n);

        while let Some(cur) = q.pop_front() {
            order.push(cur);
            for &next in &edges[cur] {
                indegree[next] -= 1;
                if indegree[next] == 0 {
                    q.push_back(next);
                }
            }
        }

        if order.len() != n {
            return Err(RuntimeError::Backend(backend::BackendError::InvalidInput(
                "cycle detected in graph".to_string(),
            )));
        }
        Ok(order)
    }

    fn two_inputs<'a>(
        &self,
        node: &Node,
        results: &'a HashMap<usize, Tensor>,
        op: &'static str,
    ) -> Result<(&'a Tensor, &'a Tensor), RuntimeError> {
        if node.inputs.len() != 2 {
            return Err(RuntimeError::Backend(backend::BackendError::InvalidInput(
                format!("{op} node {} requires 2 inputs", node.id),
            )));
        }
        let a = results.get(&node.inputs[0]).ok_or_else(|| {
            RuntimeError::Backend(backend::BackendError::InvalidInput(format!(
                "missing input {}",
                node.inputs[0]
            )))
        })?;
        let b = results.get(&node.inputs[1]).ok_or_else(|| {
            RuntimeError::Backend(backend::BackendError::InvalidInput(format!(
                "missing input {}",
                node.inputs[1]
            )))
        })?;
        Ok((a, b))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tensor::DType;

    #[test]
    fn topological_order_valid() {
        let mut g = Graph::new();
        let a = g.add_node(Op::Input(Tensor::ones(&[2, 2])), vec![]);
        let b = g.add_node(Op::Input(Tensor::ones(&[2, 2])), vec![]);
        let mm = g.add_node(Op::MatMul, vec![a, b]);
        let c = g.add_node(Op::Input(Tensor::ones(&[2, 2])), vec![]);
        let add = g.add_node(Op::Add, vec![mm, c]);

        let order = g.topological_order().expect("valid dag");
        let pos_mm = order.iter().position(|x| *x == mm).unwrap();
        let pos_add = order.iter().position(|x| *x == add).unwrap();
        assert!(pos_mm < pos_add);
    }

    #[test]
    fn execute_chain_matmul_add() {
        let mut g = Graph::new();
        let a = g.add_node(
            Op::Input(Tensor::new(
                vec![2, 2],
                DType::F32,
                vec![1.0, 2.0, 3.0, 4.0],
            )),
            vec![],
        );
        let b = g.add_node(
            Op::Input(Tensor::new(
                vec![2, 2],
                DType::F32,
                vec![5.0, 6.0, 7.0, 8.0],
            )),
            vec![],
        );
        let mm = g.add_node_on(Some(BackendKind::Cpu), Op::MatMul, vec![a, b]);
        let bias = g.add_node(Op::Input(Tensor::ones(&[2, 2])), vec![]);
        let out_id = g.add_node(Op::Add, vec![mm, bias]);

        let results = g.execute().expect("graph executes");
        let out = results.get(&out_id).unwrap();
        assert_eq!(out.data, vec![20.0, 23.0, 44.0, 51.0]);
    }

    #[test]
    fn graph_reports_unregistered_backend() {
        let mut g = Graph::new();
        let a = g.add_node(Op::Input(Tensor::ones(&[1])), vec![]);
        let b = g.add_node(Op::Input(Tensor::ones(&[1])), vec![]);
        g.add_node_on(Some(BackendKind::Metal), Op::Add, vec![a, b]);

        let err = g.execute().unwrap_err();
        assert_eq!(
            err,
            RuntimeError::Backend(backend::BackendError::UnsupportedBackend(
                BackendKind::Metal
            ))
        );
    }

    #[test]
    fn cycle_detection_works() {
        let g = Graph {
            nodes: vec![
                Node {
                    id: 0,
                    op: Op::Input(Tensor::ones(&[1])),
                    inputs: vec![1],
                    backend: None,
                },
                Node {
                    id: 1,
                    op: Op::Input(Tensor::ones(&[1])),
                    inputs: vec![0],
                    backend: None,
                },
            ],
        };
        let err = g.topological_order().unwrap_err().to_string();
        assert!(err.contains("cycle"));
    }
}
