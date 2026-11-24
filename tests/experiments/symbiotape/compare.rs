#![forbid(unsafe_code)]
mod ref_vm;

use std::{env, io::{self, BufReader, Read}};
use ref_vm::{execute, Mode, SIZE};

fn compare(count: usize, mode: Mode, input: impl Read) -> io::Result<()> {
    let mut input = BufReader::with_capacity(1024 * 1024, input);
    for case in 0..count {
        let mut record = [0; SIZE * 2 + 4];
        input.read_exact(&mut record)?;
        let tape: [u8; SIZE] = record[..SIZE].try_into().unwrap();
        let expected = &record[SIZE..SIZE * 2];
        let fuel = u16::from_le_bytes(record[SIZE * 2..SIZE * 2 + 2].try_into().unwrap());
        let active = u16::from_le_bytes(record[SIZE * 2 + 2..].try_into().unwrap());
        let actual = execute(tape, fuel, mode).map_err(io::Error::other)?;
        if actual.active != active || actual.tape != expected {
            return Err(io::Error::other(format!(
                "case {case}, fuel {fuel}: input {tape:02x?}, expected active {active}, \
                 expected {expected:02x?}, actual {actual:?}"
            )));
        }
    }
    if input.read(&mut [0; 1])? != 0 {
        return Err(io::Error::other("oracle emitted extra bytes"));
    }
    println!("{count} pairs matched: tape bytes and active operation counts");
    Ok(())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut args = env::args().skip(1);
    let mode = match args.next().as_deref() {
        Some("bff") => Mode::Headed,
        Some("bff_noheads") => Mode::Headless,
        _ => return Err("expected bff or bff_noheads".into()),
    };
    let count: usize = args.next().ok_or("expected a case count")?.parse()?;
    if count == 0 {
        return Err("case count must be positive".into());
    }
    compare(count, mode, io::stdin().lock())?;
    Ok(())
}
