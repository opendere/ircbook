def pretty_list(l):
    """Take a list, print its members separated by commas, and put and before the last."""
    if len(l) == 0:
        return ""
    elif len(l) == 1:
        return str(l[0])
    elif len(l) == 2:
        return str(l[0]) + " and " + str(l[1])
    else:
        s = ""
        for i in l[:-1]:
            s += str(i) + ", "
        s += "and " + str(l[-1])
        return s
