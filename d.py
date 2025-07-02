def merge_documents(file1_path, file2_path, output_file_path):
    # Function to read file and return paragraphs (split by double newlines)
    def read_file_as_paragraphs(file_path):
        with open(file_path, 'r') as file:
            content = file.read()
        # Split content into paragraphs by double newlines, strip and clean up
        return [para.strip() for para in content.split("\n\n") if para.strip()]

    # Function to merge paragraphs by comparing exact content and removing duplicates
    def merge_paragraphs(file1_paragraphs, file2_paragraphs):
        seen = set()  # Set to track unique paragraphs (as whole)
        merged_paragraphs = []

        # Function to add unique paragraphs by comparing exact content
        def add_unique_paragraphs(paragraphs):
            for para in paragraphs:
                if para not in seen:  # Check if the exact paragraph already exists
                    seen.add(para)  # Mark this paragraph as seen
                    merged_paragraphs.append(para)  # Add it to the merged list

        # Add paragraphs from both files
        add_unique_paragraphs(file1_paragraphs)
        add_unique_paragraphs(file2_paragraphs)

        return merged_paragraphs

    # Read paragraphs from both files
    file1_paragraphs = read_file_as_paragraphs(file1_path)
    file2_paragraphs = read_file_as_paragraphs(file2_path)

    # Merge paragraphs from both files
    merged_paragraphs = merge_paragraphs(file1_paragraphs, file2_paragraphs)

    # Write the merged paragraphs to the output file
    with open(output_file_path, 'w') as output_file:
        output_file.write("\n\n".join(merged_paragraphs))

    print(f"Documents merged successfully into {output_file_path}")

# Example usage
file1 = 'C:/Users/Administrator/Desktop/a.txt'  # Replace with your actual file path
file2 = 'C:/Users/Administrator/Desktop/b.txt'  # Replace with your actual file path
output_file = 'combined.txt'  # Replace with your desired output file path

merge_documents(file1, file2, output_file)
