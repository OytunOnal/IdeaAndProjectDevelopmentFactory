async def write_project_file(project_id: str, file_path: str, content: str) -> dict:
    """Write a generated file to the project's file storage."""
    # TODO: Store in database (project_files table)
    return {"file_path": file_path, "version": 1, "status": "draft"}
