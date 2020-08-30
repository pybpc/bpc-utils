def read_text_file(filename, encoding='utf-8'):
    """Read text file."""
    with open(filename, 'r', encoding=encoding) as file:
        return file.read()


def write_text_file(filename, content, encoding='utf-8'):
    """Write text file."""
    with open(filename, 'w', encoding=encoding) as file:
        file.write(content)
