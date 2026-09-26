from langchain_text_splitters import RecursiveCharacterTextSplitter


def chunk_code(parsed_file: dict) -> list[dict]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=[
            "\nclass ",
            "\ndef ",
            "\nfunction ",
            "\n\n",
            "\n",
            " ",
            "",
        ],
        add_start_index=True,
    )

    documents = splitter.create_documents(
        [parsed_file["content"]]
    )

    results = []

    for index, document in enumerate(documents):
        start_char = document.metadata["start_index"]
        end_char = start_char + len(document.page_content)

        start_line = (
            parsed_file["content"][:start_char].count("\n") + 1
        )

        end_line = (
            parsed_file["content"][:end_char].count("\n") + 1
        )

        results.append(
            {
                "chunk_index": index,
                "file_path": parsed_file["file_path"],
                "file_name": parsed_file["file_name"],
                "language": parsed_file["language"],
                "content": document.page_content,
                "start_line": start_line,
                "end_line": end_line,
            }
        )

    return results