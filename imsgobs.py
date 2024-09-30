import sqlite3
import os
from datetime import datetime
import shutil
import subprocess  # To use sips for conversion

# Path to iMessages chat database
db_path = os.path.expanduser('~/Library/Messages/chat.db')

# Path to the base of the iMessages attachments
attachments_base_path = os.path.expanduser('~/Library/Messages/Attachments')
attachment_save_path = os.path.expanduser("") # INSERT OBSIDIAN VAULT ATTACHMENTS PATH HERE

# Path to the daily markdown file
journal_path = os.path.expanduser("") # INSERT OBSIDIAN VAULT NOTES PATH HERE
today_date = datetime.now().strftime("%Y.%m.%d")
markdown_filename = f"{today_date}.md"
markdown_filepath = os.path.join(journal_path, markdown_filename)

# Hardcoded phone number
contact_handle = "+..." #INSERT CONTACT NUMBER

# Query to fetch today's messages from the specific contact, including attachments
query = """
SELECT
    datetime(message.date/1000000000 + strftime('%s', '2001-01-01'), 'unixepoch', 'localtime') as message_date,
    handle.id as sender,
    message.text,
    attachment.filename,
    attachment.mime_type
FROM
    message
JOIN
    handle ON message.handle_id = handle.ROWID
LEFT JOIN
    message_attachment_join ON message.ROWID = message_attachment_join.message_id
LEFT JOIN
    attachment ON attachment.ROWID = message_attachment_join.attachment_id
WHERE
    handle.id = ? AND date(message.date/1000000000 + strftime('%s', '2001-01-01'), 'unixepoch', 'localtime') = ?
ORDER BY
    message.date ASC
"""

# Connect to the database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute(query, (contact_handle, today_date.replace(".", "-")))  # Adjust the date format for the query

# Fetch all the messages
messages = cursor.fetchall()

# Check if today's markdown file exists, create it if not
if not os.path.exists(markdown_filepath):
    with open(markdown_filepath, 'w', encoding='utf-8') as file:
        file.write(f"\n")

# Read existing content to avoid duplicates
with open(markdown_filepath, 'r', encoding='utf-8') as file:
    existing_content = file.read()

# Prepare the content to append
new_content = ""
image_counter = 1  # Counter for renaming images

if messages:
    # Dictionary to store messages by exact timestamp (with seconds)
    grouped_messages = {}

    for message in messages:
        message_date, sender, text, attachment_filename, mime_type = message
        
        # Use the full timestamp including seconds for tracking, but not for display
        formatted_time = message_date

        # Initialize the content for this timestamp if not already present
        if formatted_time not in grouped_messages:
            grouped_messages[formatted_time] = []

        # Add text or attachment information to the grouped content
        if text:
            grouped_messages[formatted_time].append(text)

        # If there's an attachment (e.g., an image in HEIC format)
        if attachment_filename:
            # Remove the incorrect prefix if it exists
            if attachment_filename.startswith("~/Library/Messages/Attachments/"):
                attachment_filename = attachment_filename.replace("~/Library/Messages/Attachments/", "")

            # Full path of the attachment (including subdirectories)
            attachment_full_path = os.path.join(attachments_base_path, attachment_filename)

            # Correct the path by removing potential user directory issues
            attachment_full_path = os.path.normpath(attachment_full_path)

            # Check if the file exists in its original location before attempting to copy
            if os.path.exists(attachment_full_path):
                # Copy the original HEIC file first
                extension = os.path.splitext(attachment_filename)[1]
                original_file = f"{today_date}_screen_{image_counter}{extension}"
                original_dest_filename = os.path.join(attachment_save_path, original_file)
                
                # Create directories if they don't exist
                if not os.path.exists(attachment_save_path):
                    os.makedirs(attachment_save_path)

                # Copy the original image
                try:
                    shutil.copy(attachment_full_path, original_dest_filename)

                    # Now convert the copied HEIC image to PNG using sips
                    if extension.lower() in ['.heic', '.heif']:
                        png_filename = os.path.splitext(original_dest_filename)[0] + ".png"

                        # Use sips to convert the image
                        subprocess.run(["sips", "-s", "format", "png", original_dest_filename, "--out", png_filename])

                        # After conversion, delete the original HEIC file
                        os.remove(original_dest_filename)

                        # Use Obsidian format with |300 for the image reference in markdown
                        grouped_messages[formatted_time].append(f"![[{os.path.basename(png_filename)}|300]]")
                    else:
                        # For non-HEIC images, use the original format and add |300
                        grouped_messages[formatted_time].append(f"![[{original_file}|300]]")

                    image_counter += 1  # Increment the image counter
                except Exception as e:
                    grouped_messages[formatted_time].append(f"[Image could not be copied or converted: {e}]")
            else:
                grouped_messages[formatted_time].append(f"[Attachment not found: {attachment_full_path}]")

    # Build the content to append (without timestamps)
    for _, contents in grouped_messages.items():
        entry = "\n".join(contents) + "\n\n"
        
        # Append the entry only if it's not already in the file
        if entry not in existing_content:
            new_content += entry

# Append new content to the markdown file if there is any
if new_content:
    with open(markdown_filepath, 'a', encoding='utf-8') as file:
        file.write(new_content)

# Close the database connection
conn.close()

print(f"Content added to: {markdown_filepath}")

