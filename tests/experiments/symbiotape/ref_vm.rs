#![forbid(unsafe_code)]
//! Independent scalar implementation of the pinned CuBFF pair semantics.

pub const SIZE: usize = 128;
pub const MAX_FUEL: u16 = 8192;

#[derive(Clone, Copy)]
pub enum Mode {
    Headed,
    Headless,
}

#[derive(Debug, PartialEq, Eq)]
pub struct Run {
    pub tape: [u8; SIZE],
    pub fetched: u16,
    pub active: u16,
}

/// Scan the current tape, since earlier operations may have changed brackets.
fn matching(tape: &[u8; SIZE], pc: usize, forward: bool) -> Option<usize> {
    let (step, opening, closing) = if forward {
        (1, b'[', b']')
    } else {
        (-1, b']', b'[')
    };
    let mut cursor = pc as isize;
    let mut depth = 1;
    loop {
        cursor += step;
        let byte = *tape.get(usize::try_from(cursor).ok()?)?;
        if byte == opening {
            depth += 1;
        } else if byte == closing {
            depth -= 1;
            if depth == 0 {
                return Some(cursor as usize);
            }
        }
    }
}

pub fn execute(mut tape: [u8; SIZE], fuel: u16, mode: Mode) -> Result<Run, &'static str> {
    if fuel > MAX_FUEL {
        return Err("fuel exceeds the Stage A cap");
    }
    let (mut read, mut write, mut pc) = match mode {
        Mode::Headed => (usize::from(tape[0]) % SIZE, usize::from(tape[1]) % SIZE, 2),
        Mode::Headless => (0, 0, 0),
    };
    let mut fetched = 0;
    let mut active = 0;
    while pc < SIZE && fetched < fuel {
        fetched += 1;
        let byte = tape[pc];
        match byte {
            b'>' => read = (read + 1) % SIZE,
            b'<' => read = (read + SIZE - 1) % SIZE,
            b'}' => write = (write + 1) % SIZE,
            b'{' => write = (write + SIZE - 1) % SIZE,
            b'+' => tape[read] = tape[read].wrapping_add(1),
            b'-' => tape[read] = tape[read].wrapping_sub(1),
            b'.' => tape[write] = tape[read],
            b',' => tape[read] = tape[write],
            b'[' | b']' => {
                let forward = byte == b'[';
                if (tape[read] == 0) == forward {
                    match matching(&tape, pc, forward) {
                        Some(pair) => pc = pair,
                        None => {
                            active += 1;
                            break;
                        }
                    }
                }
            }
            _ => {
                pc += 1;
                continue;
            }
        }
        active += 1;
        pc += 1;
    }
    Ok(Run { tape, fetched, active })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn zero_and_unknown_bytes_consume_fuel_and_continue() {
        let mut tape = [0; SIZE];
        tape[..6].copy_from_slice(&[40, 50, 0, 255, b'+', b'.']);
        let run = execute(tape, 4, Mode::Headed).unwrap();
        assert_eq!((run.fetched, run.active, run.tape[40], run.tape[50]), (4, 2, 1, 1));
        let run = execute(tape, 2, Mode::Headed).unwrap();
        assert_eq!((run.fetched, run.active, run.tape[40]), (2, 0, 0));
    }

    #[test]
    fn arithmetic_and_both_heads_wrap() {
        let mut tape = [0; SIZE];
        tape[..8].copy_from_slice(&[128, 255, b'<', b'-', b'}', b'.', b'{', b',']);
        let run = execute(tape, 6, Mode::Headed).unwrap();
        assert_eq!((run.tape[0], run.tape[127]), (255, 255));
    }

    #[test]
    fn instruction_mutation_changes_the_forward_bracket_scan() {
        let mut tape = [0; SIZE];
        tape[..9].copy_from_slice(&[60, 5, b'.', b'>', b'[', b'.', b'-', b']', b'+']);
        tape[60] = b'[';
        let run = execute(tape, 16, Mode::Headed).unwrap();
        assert_eq!(run.tape[5], b'[');
        assert_eq!(run.tape[61], 0);
        assert_eq!(run.active, 3);
    }

    #[test]
    fn backward_branch_does_not_refetch_open_and_stops_when_clear() {
        let mut tape = [0; SIZE];
        tape[..6].copy_from_slice(&[60, 63, b'[', b'-', b']', b'+']);
        tape[60] = 2;
        let run = execute(tape, 6, Mode::Headed).unwrap();
        assert_eq!((run.fetched, run.active, run.tape[60]), (6, 6, 1));
    }

    #[test]
    fn headless_starts_at_zero_and_can_modify_its_first_instruction() {
        let mut tape = [0; SIZE];
        tape[..2].copy_from_slice(b"+.");
        let headless = execute(tape, 2, Mode::Headless).unwrap();
        let headed = execute(tape, 2, Mode::Headed).unwrap();
        assert_eq!((headless.tape[0], headless.active), (b',', 2));
        assert_eq!((headed.tape[0], headed.active), (b'+', 0));
    }

    #[test]
    fn malformed_and_nonterminating_tapes_remain_bounded() {
        let mut tape = [0; SIZE];
        tape[..5].copy_from_slice(&[40, 50, b']', b'+', 0]);
        tape[40] = 1;
        let run = execute(tape, MAX_FUEL, Mode::Headed).unwrap();
        assert_eq!((run.active, run.fetched), (1, 1));
        tape[2] = b'[';
        tape[3] = b']';
        let run = execute(tape, MAX_FUEL, Mode::Headed).unwrap();
        assert_eq!((run.active, run.fetched), (MAX_FUEL, MAX_FUEL));
        assert!(execute(tape, MAX_FUEL + 1, Mode::Headed).is_err());
        assert_eq!(execute(tape, 0, Mode::Headed).unwrap().tape, tape);
    }
}
