from app.services.git_metadata import git_metadata_service


SAMPLE_DIFF = """diff --git a/app/auth.py b/app/auth.py
index 1234567..89abcdef 100644
--- a/app/auth.py
+++ b/app/auth.py
@@ -10,3 +10,5 @@ def login():
+    token = generate_token()
+    return token
diff --git a/app/old_module.py b/app/old_module.py
deleted file mode 100644
index 9999999..0000000 100644
--- a/app/old_module.py
+++ /dev/null
@@ -1,2 +0,0 @@
-def deprecated():
-    pass
diff --git a/app/new_service.py b/app/new_service.py
new file mode 100644
index 0000000..1111111 100644
--- /dev/null
+++ b/app/new_service.py
@@ -0,0 +1,3 @@
+class NewService:
+    pass
+
"""

SAMPLE_NUMSTAT = """2\t0\tapp/auth.py
0\t2\tapp/old_module.py
3\t0\tapp/new_service.py
"""


def test_parse_patch_files():
    parsed_files = git_metadata_service.parse_patch_files(SAMPLE_DIFF, SAMPLE_NUMSTAT)

    assert len(parsed_files) == 3

    # Modified file
    auth_diff = next(f for f in parsed_files if f.new_path == "app/auth.py")
    assert auth_diff.change_type == "modified"
    assert auth_diff.additions == 2
    assert auth_diff.deletions == 0
    assert "token = generate_token()" in auth_diff.patch_text

    # Deleted file
    deleted_diff = next(f for f in parsed_files if f.new_path == "app/old_module.py")
    assert deleted_diff.change_type == "deleted"
    assert deleted_diff.deletions == 2

    # Added file
    new_diff = next(f for f in parsed_files if f.new_path == "app/new_service.py")
    assert new_diff.change_type == "added"
    assert new_diff.additions == 3
    assert new_diff.old_path is None
