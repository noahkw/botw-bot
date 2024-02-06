import typing


def get_words_in_message(message: str) -> list[str]:
    return [word.strip() for word in message.split() if word.strip()]


class TrieNode:
    children: dict[str, "TrieNode"]

    def __init__(self):
        self.children = {}
        self.is_end_of_word = False

    @staticmethod
    def build(words: typing.Iterable[str]) -> "TrieNode":
        root = TrieNode()

        for word in words:
            node = root

            for substr in get_words_in_message(word):
                node = node.children.setdefault(substr, TrieNode())

            node.is_end_of_word = True

        return root

    def search(self, message: str) -> bool:
        node = self

        for index, char in enumerate(get_words_in_message(message)):
            node = node.children.get(char)

            if node is None:
                node = self
            elif node.is_end_of_word:
                return True

        return False

    def match_message(self, message: str) -> bool:
        for word in message.split() + [message]:
            word_stripped = word.strip()

            if self.search(word_stripped):
                return True

        return False


def test():
    banned_words = [
        "bad",
        "bad word",
        "very bad",
        "red velvet sucks",
        "theoreticallybad",
        "really awful",
    ]

    messages = [
        "very bad word",
        "this message is ok",
        "b badbad b",
        "very   bad",
        "bla red velvet sucks jk",
        "te theoreticallybadbutnowisnt st",
        "that is really awful lol",
    ]

    trie = TrieNode.build(banned_words)

    print(f"bad words: {banned_words}")
    for message in messages:
        print(f'Message: "{message}", bad? {trie.match_message(message)}')


if __name__ == "__main__":
    test()
