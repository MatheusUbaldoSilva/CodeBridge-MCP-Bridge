"""Experimental process-local resident embedding lifecycle."""
import threading
from rag.models.artifact_install import resolve_selected_model_path
from rag.models.code_artifact_install import resolve_selected_code_model_path
from rag.models.embedding import TextEmbeddingClient
from rag.models.code_embedding import CodeEmbeddingClient,CodeRetrievalTask
from rag.models.lifecycle import LlamaServerConfig,TextModelLifecycle
from rag.models.code_lifecycle import CodeModelLifecycle,build_code_server_config

class ResidentEmbeddingPool:
 def __init__(self):
  self.lock=threading.RLock()
  self.text_lifecycle=None
  self.code_lifecycle=None
 def embed_text(self,query,exe):
  with self.lock:
   if self.text_lifecycle is None:
    instance=TextModelLifecycle(LlamaServerConfig(executable_path=exe,model_path=resolve_selected_model_path(),port=0,gpu_layers=99,device="CUDA0"))
    instance.load(timeout_seconds=90)
    self.text_lifecycle=instance
   return TextEmbeddingClient(self.text_lifecycle).embed_query(query).values
 def embed_code(self,query,exe):
  with self.lock:
   if self.code_lifecycle is None:
    instance=CodeModelLifecycle(build_code_server_config(executable_path=exe,model_path=resolve_selected_code_model_path(),port=0,gpu_layers=99,device="CUDA0"))
    instance.load(timeout_seconds=90)
    self.code_lifecycle=instance
   return CodeEmbeddingClient(self.code_lifecycle).embed_query(CodeRetrievalTask.NL2CODE,query).values
 def close(self):
  with self.lock:
   for attr in ("code_lifecycle","text_lifecycle"):
    obj=getattr(self,attr)
    setattr(self,attr,None)
    if obj is not None:obj.unload(timeout_seconds=15)

resident_pool=ResidentEmbeddingPool()
