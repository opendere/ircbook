from util.stringutils import pretty_list


def test_pretty_list_empty():
    assert (pretty_list([]) == "")


def test_pretty_list_one():
    assert (pretty_list(["hello"]) == "hello")


def test_pretty_list_two():
    assert (pretty_list(["Romeo", "Julie"]) == "Romeo and Julie")


def test_pretty_list_three():
    assert (pretty_list(["Curly", "Larry", "Moe"]) == "Curly, Larry, and Moe")
