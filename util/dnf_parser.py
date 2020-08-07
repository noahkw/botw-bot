def strip_list(l):
    return [x.strip() for x in l]


class DNFParser:
    def __init__(self, exp):
        self._exp = exp
        self._parsed = self._parse_expression()

    def _parse_expression(self):
        if len(self._exp) < 1:
            return []

        # First, split on OR terms to get all AND terms/terminals
        and_terms = self._exp.split('or')

        # Then split on AND
        terminalized = [and_term.split('and') for and_term in and_terms]

        # remove leading and trailing whitespace from the terminals
        terminalized_stripped = list(map(strip_list, terminalized))

        # convert to actual terminals
        terminals = list(map(Terminal.from_list, terminalized_stripped))
        return terminals

    def evaluate(self, collection):
        return any([self._evaluate_and_term(and_term, collection) for and_term in self._parsed])

    @staticmethod
    def _evaluate_and_term(and_term, collection):
        return all([terminal.check(collection) for terminal in and_term])


class Terminal:
    def __init__(self, content):
        if content[0] == '!':
            self.content = content[1:]
            self.negated = True
        else:
            self.content = content
            self.negated = False

    def check(self, collection):
        if self.negated:
            return self.content not in collection
        else:
            return self.content in collection

    @staticmethod
    def from_list(terminals):
        return [Terminal(x) for x in terminals]

    def __repr__(self):
        return f'<"{self.content}", neg: {self.negated}>'


if __name__ == '__main__':
    test_sets = [
        {'tree', 'car', 'wall'},
        {'tree', 'car'},
        {'2020', 'car', 'person'},
        {'tree', 'person'},
        {'tree man'}
    ]

    test_string = 'tree and !person or 2020 or tree man'

    parser = DNFParser(test_string)
    for i, test_set in enumerate(test_sets):
        if parser.evaluate(test_set):
            print(f'Match found in test set {i}!')
