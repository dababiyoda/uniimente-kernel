"""Disposable worker protocol. No user-supplied executable expressions."""
import json
import sys


def main():
    # Native solver address space includes mapped libraries. Bound CPU and address space.
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (12, 12))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    request = json.loads(sys.stdin.buffer.read(131073))
    if sys.argv[1] == 'verify':
        from cortex.seed.verify import verify
        answer = verify(request['claim'], request['artifact'])
    elif sys.argv[1] == 'compute':
        from cortex.seed.methods import compute
        answer = compute(request['claim'], request['budget_ms'])
    else:
        raise ValueError('unknown worker mode')
    print(json.dumps(answer, allow_nan=False))


if __name__ == '__main__':
    main()
