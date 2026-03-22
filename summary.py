import glob
import os

def create_summary():
    # 1. Setup paths
    target_folder = "misc"
    output_file = os.path.join(target_folder, "SUMMARY.md")
    
    # Create the /misc/ directory if it doesn't exist
    if not os.path.exists(target_folder):
        os.makedirs(target_folder)
        print(f"Created directory: {target_folder}")

    # 2. Find all .py and .md files
    # We use recursive=True to find files in subfolders
    files = glob.glob("**/*.py", recursive=True) + glob.glob("**/*.md", recursive=True)
    
    with open(output_file, "w", encoding="utf-8") as outfile:
        outfile.write("# Project Summary\n\n")
        
        for file_path in files:
            # Skip the output file itself if it's already in the list
            if file_path == output_file:
                continue
                
            outfile.write(f"## File: {file_path}\n")
            outfile.write("```\n")
            
            try:
                with open(file_path, "r", encoding="utf-8") as infile:
                    outfile.write(infile.read())
            except Exception as e:
                outfile.write(f"Error reading file: {e}")
                
            outfile.write("\n```\n\n---\n\n")
            print(f"Added: {file_path}")

    print(f"\nDone! Summary created at: {output_file}")

if __name__ == "__main__":
    create_summary()
