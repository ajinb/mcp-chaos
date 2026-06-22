from mcp_chaos.cli import build_parser, cmd_demo


def test_parser_has_subcommands():
    parser = build_parser()
    args = parser.parse_args(["demo"])
    assert args.command == "demo"
    args = parser.parse_args(["proxy", "stdio", "--", "my-server", "--flag"])
    assert args.command == "proxy"
    assert args.transport == "stdio"
    assert args.server_cmd == ["my-server", "--flag"]


def test_cmd_demo_prints_two_rows(capsys):
    cmd_demo(tasks=50, fanout=8, error_rate=0.02, seed=1)
    out = capsys.readouterr().out
    assert "no resilience" in out
    assert "with resilience" in out
    assert "TCAF=8.0" in out
