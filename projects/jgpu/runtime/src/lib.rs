pub mod graph;

use crossbeam_channel::{unbounded, Receiver, Sender};
use std::thread;
use tensor::Tensor;

#[derive(Debug)]
pub enum Command {
    MatMul { a: Tensor, b: Tensor, resp: Sender<Tensor> },
    Shutdown,
}

pub struct Runtime {
    tx: Sender<Command>,
    worker: Option<thread::JoinHandle<()>>,
}

impl Runtime {
    pub fn start() -> Self {
        let (tx, rx) = unbounded::<Command>();
        let worker = thread::spawn(move || executor_loop(rx));
        Self { tx, worker: Some(worker) }
    }

    pub fn submit_matmul(&self, a: Tensor, b: Tensor) -> Receiver<Tensor> {
        let (resp_tx, resp_rx) = unbounded();
        self.tx.send(Command::MatMul { a, b, resp: resp_tx }).expect("runtime worker available");
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

fn executor_loop(rx: Receiver<Command>) {
    while let Ok(cmd) = rx.recv() {
        match cmd {
            Command::MatMul { a, b, resp } => {
                let out = kernels::matmul_parallel(&a, &b);
                let _ = resp.send(out);
            }
            Command::Shutdown => break,
        }
    }
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
        let out = rx.recv().expect("result");
        assert_eq!(out.data, vec![19.0, 22.0, 43.0, 50.0]);
    }
}
