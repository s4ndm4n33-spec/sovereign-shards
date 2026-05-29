use std::collections::HashMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Temperature {
    Hot,
    Warm,
    Cold,
}

#[derive(Debug, Clone)]
pub struct Allocation {
    pub id: u64,
    pub bytes: usize,
    pub ref_count: usize,
    pub temp: Temperature,
}

#[derive(Default)]
pub struct Allocator {
    next_id: u64,
    table: HashMap<u64, Allocation>,
}

impl Allocator {
    pub fn allocate(&mut self, bytes: usize, temp: Temperature) -> u64 {
        let id = self.next_id;
        self.next_id += 1;
        self.table.insert(id, Allocation { id, bytes, ref_count: 1, temp });
        id
    }

    pub fn retain(&mut self, id: u64) {
        if let Some(a) = self.table.get_mut(&id) {
            a.ref_count += 1;
        }
    }

    pub fn release(&mut self, id: u64) {
        if let Some(a) = self.table.get_mut(&id) {
            if a.ref_count > 1 {
                a.ref_count -= 1;
            } else {
                self.table.remove(&id);
            }
        }
    }

    pub fn allocated_bytes(&self) -> usize {
        self.table.values().map(|a| a.bytes).sum()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn allocation_lifecycle() {
        let mut alloc = Allocator::default();
        let id = alloc.allocate(1024, Temperature::Hot);
        assert_eq!(alloc.allocated_bytes(), 1024);
        alloc.retain(id);
        alloc.release(id);
        assert_eq!(alloc.allocated_bytes(), 1024);
        alloc.release(id);
        assert_eq!(alloc.allocated_bytes(), 0);
    }
}
