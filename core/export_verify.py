"""Did a companion exporter actually write its file?

None of the companion exporters says so through its return value:

* RE Mesh Editor's ``exportfile`` (mesh, fbxskel, sfur) and MHW Model Editor's
  mod3 / mrl3 / ctc exports return ``{'FINISHED'}`` whether or not the file was
  written -- a mesh refused for MaxWeightsPerVertexExceeded or NoMeshesInCollection
  only reports, then finishes.
* ``re_mdf.exportfile`` returns ``{'CANCELLED'}`` with an INFO-level report,
  which ``bpy.ops`` does not raise on.

So a batch export took every call as a success: the previous file stayed on disk,
the summary said "0 failed", and RE4/RE9's export cache then copied that stale file
to every other entry bound to the same collection.

All of these exporters write ``self.filepath`` exactly as given when called from
Python (the path rewriting lives in their ``invoke``), so comparing the target's
stat before and after the call is a reliable answer.
"""

import os


class ExportNotWritten(RuntimeError):
    """The exporter returned, but the file it was asked for was not written."""


def _stamp(path):
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


def checked(filepath, call):
    """Run ``call()`` (a companion export) and raise unless it wrote *filepath*.

    Raises ExportNotWritten when the operator did not finish, when no file
    exists afterwards, or when an existing file was left untouched.  Callers
    already count exceptions as failures, which is the point.
    """
    before = _stamp(filepath)
    result = call()
    after = _stamp(filepath)
    if result is not None and 'FINISHED' not in result:
        raise ExportNotWritten(
            f"exporter returned {sorted(result)}; see its messages above")
    if after is None:
        raise ExportNotWritten("exporter finished but wrote no file; see its messages above")
    if after == before:
        raise ExportNotWritten(
            "exporter finished but left the existing file unchanged; see its messages above")
    return result
