import sys
import time
import threading
import subprocess
from flask import Blueprint, request, jsonify
from dashboard.core import get_db, REPO_ROOT

rag_bp = Blueprint("rag", __name__)

@rag_bp.route("/api/rag/bases", methods=["GET"])
def api_rag_list_bases():
    """Lista todas las bases de conocimiento LanceDB disponibles (multi-tenant)."""
    try:
        from rag_engine import list_knowledge_bases
        bases = list_knowledge_bases()
        return jsonify({"success": True, "bases": bases})
    except Exception as e:
        return jsonify({"error": f"Error listando bases RAG: {str(e)}"}), 500


@rag_bp.route("/api/rag/bases", methods=["POST"])
def api_rag_create_base():
    """Crea una nueva base de conocimiento para una empresa, opcionalmente clonando dominios de otra base."""
    try:
        from rag_engine import create_knowledge_base
        data = request.get_json() or {}
        empresa = data.get("empresa", "").strip()
        table_name = data.get("table_name", "").strip() or None
        clone_from = data.get("clone_from", "").strip() or None
        clone_themes = data.get("clone_themes", None)
        
        if not empresa and not table_name:
            return jsonify({"error": "Debe proporcionar el nombre de la empresa o el nombre de la tabla."}), 400
            
        res = create_knowledge_base(
            table_name=table_name or empresa,
            clone_from=clone_from,
            clone_themes=clone_themes
        )
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": f"Error creando base RAG: {str(e)}"}), 500


@rag_bp.route("/api/rag/bases/clone-domain", methods=["POST"])
def api_rag_clone_domain():
    """Clona los fragmentos de un dominio temático desde una base origen a una base destino en memoria (Arrow)."""
    try:
        from rag_engine import clone_knowledge_domain
        data = request.get_json() or {}
        source_table = data.get("source_table", "").strip()
        target_table = data.get("target_table", "").strip()
        theme = data.get("theme", "").strip()
        
        if not source_table or not target_table or not theme:
            return jsonify({"error": "Los parámetros 'source_table', 'target_table' y 'theme' son obligatorios."}), 400
            
        res = clone_knowledge_domain(source_table, target_table, theme)
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": f"Error clonando dominio: {str(e)}"}), 500


@rag_bp.route("/api/rag/bases/<table_name>", methods=["DELETE"])
def api_rag_delete_base(table_name):
    """Elimina una base de conocimiento tenant en LanceDB (protegiendo teccam_knowledge_base)."""
    try:
        from rag_engine import delete_knowledge_base
        res = delete_knowledge_base(table_name)
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": f"Error eliminando base: {str(e)}"}), 500


@rag_bp.route("/api/rag/stats", methods=["GET"])
def api_rag_stats():
    """Obtiene métricas y estado actual de la base de conocimiento LanceDB (por defecto o por empresa)."""
    try:
        from rag_engine import get_rag_stats
        table_name = request.args.get("table_name") or None
        stats = get_rag_stats(table_name=table_name)
        
        try:
            db = get_db()
            query = {}
            if table_name:
                query = {"$or": [{"table_name": table_name}, {"empresa": table_name}]}
            log_entry = db.rag_sync_logs.find_one(query, sort=[("timestamp", -1)])
            if not log_entry and table_name:
                log_entry = db.rag_sync_logs.find_one(sort=[("timestamp", -1)])
            if log_entry:
                ts = log_entry.get("timestamp")
                stats["last_sync"] = {
                    "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                    "status": log_entry.get("status", "success"),
                    "duration_sec": log_entry.get("duration_sec", 0),
                    "docs_synced_count": log_entry.get("docs_synced_count", 0),
                    "total_chunks": log_entry.get("total_chunks_in_db", 0)
                }
            else:
                stats["last_sync"] = None
        except Exception:
            stats["last_sync"] = None
            
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": f"Error obteniendo estadísticas RAG: {str(e)}"}), 500


@rag_bp.route("/api/rag/sync", methods=["POST"])
def api_rag_sync():
    """Dispara una sincronización diferencial de Teccam PDF -> LanceDB en segundo plano utilizando el orquestador de VRAM."""
    try:
        data = request.get_json(silent=True) or {}
        force = data.get("force", False)
        pause_llm = data.get("pause_llm", None)
        empresa = data.get("empresa", "").strip() or None
        table_name = data.get("table_name", "").strip() or None
        
        if not empresa:
            if table_name == "teccam_knowledge_base" or not table_name:
                empresa = "TECCAM S.R.L."
            elif table_name.startswith("kb_"):
                empresa = table_name.replace("kb_", "").replace("_", " ").title()
        
        def run_sync():
            try:
                sync_script = REPO_ROOT / "sync_rag_scheduled.sh"
                cmd = ["sudo", "/bin/bash", str(sync_script)]
                if force:
                    cmd.append("--force")
                if pause_llm is True:
                    cmd.append("--pause-llm")
                elif pause_llm is False:
                    cmd.append("--no-pause-llm")
                if empresa:
                    cmd.extend(["--empresa", empresa])
                if table_name:
                    cmd.extend(["--table-name", table_name])
                subprocess.run(cmd, check=True)
            except Exception as se:
                print(f"❌ Error en background sync con orquestador: {se}", file=sys.stderr)
                
        thread = threading.Thread(target=run_sync, daemon=True)
        thread.start()
        
        desc_empresa = f" para la empresa '{empresa}'" if empresa else ""
        if pause_llm is True:
            msg = f"Sincronización RAG{desc_empresa} iniciada. El LLM se pausará temporalmente para proteger la VRAM y se reactivará al terminar."
        else:
            msg = f"Sincronización RAG{desc_empresa} iniciada en caliente con cero downtime (LLM activo)."
            
        return jsonify({
            "status": "started",
            "message": msg
        })
    except Exception as e:
        return jsonify({"error": f"Error al iniciar sincronización: {str(e)}"}), 500


@rag_bp.route("/api/rag/sync-metadata", methods=["POST"])
def api_rag_sync_metadata():
    """Actualiza en milisegundos y en caliente la metadata (vigencia, fecha_publicacion) desde Teccam PDF sin tocar GPU."""
    try:
        from app_rag_sync import fetch_teccam_documents_index
        from rag_engine import get_lancedb, TABLE_NAME

        data = request.get_json(silent=True) or {}
        empresa = data.get("empresa", "").strip() or None
        target_table_name = data.get("table_name", "").strip() or TABLE_NAME
        
        if not empresa:
            if target_table_name == TABLE_NAME:
                empresa = "TECCAM S.R.L."
            elif target_table_name.startswith("kb_"):
                empresa = target_table_name.replace("kb_", "").replace("_", " ").title()

        remote_docs = fetch_teccam_documents_index(empresa=empresa)
        if not remote_docs:
            return jsonify({"error": "No se pudo conectar con la API de Teccam PDF o no retornó documentos."}), 502

        db = get_lancedb()
        if target_table_name not in db.table_names():
            return jsonify({"error": f"La tabla '{target_table_name}' no existe en LanceDB."}), 404
        table = db.open_table(target_table_name)

        if "doc_vigencia" not in table.schema.names or "doc_fecha_publicacion" not in table.schema.names:
            table.add_columns({"doc_vigencia": "'NA (no aplica)'", "doc_fecha_publicacion": "cast(null as string)"})
            table = db.open_table(target_table_name)

        updated_count = 0
        for doc in remote_docs:
            doc_id = doc.get("id")
            if not doc_id:
                continue
            vig = doc.get("vigencia") or "NA (no aplica)"
            fpub = doc.get("fecha_publicacion") or ""
            clean_id = doc_id.replace("'", "''")
            table.update(
                where=f"doc_id = '{clean_id}'",
                values={
                    "doc_vigencia": vig,
                    "doc_fecha_publicacion": str(fpub)
                }
            )
            updated_count += 1

        return jsonify({
            "success": True,
            "updated_count": updated_count,
            "table_name": target_table_name,
            "message": f"Metadata de {updated_count} documentos actualizada en '{target_table_name}' en milisegundos (sin pausa de LLM ni uso de GPU)."
        })
    except Exception as e:
        return jsonify({"error": f"Error actualizando metadata: {str(e)}"}), 500


@rag_bp.route("/api/rag/settings", methods=["GET", "POST"])
def api_rag_settings():
    """Lee o actualiza la configuración global de RAG (estado, dominios activos y modelo cloud para RAG)."""
    try:
        from rag_engine import get_rag_settings, save_rag_settings
        if request.method == "POST":
            data = request.get_json() or {}
            active_topics = data.get("active_topics", None)
            enabled = data.get("enabled", None)
            cloud_rag_provider_id = data.get("cloud_rag_provider_id", None)
            cloud_rag_provider_name = data.get("cloud_rag_provider_name", None)
            cloud_rag_model_id = data.get("cloud_rag_model_id", None)
            
            success = save_rag_settings(
                active_topics=active_topics,
                enabled=enabled,
                cloud_rag_provider_id=cloud_rag_provider_id,
                cloud_rag_provider_name=cloud_rag_provider_name,
                cloud_rag_model_id=cloud_rag_model_id
            )
            settings = get_rag_settings()
            return jsonify({"success": success, **settings})
        else:
            settings = get_rag_settings()
            return jsonify(settings)
    except Exception as e:
        return jsonify({"error": f"Error en settings RAG: {str(e)}"}), 500


@rag_bp.route("/api/rag/search", methods=["POST"])
def api_rag_search():
    """Ejecuta una búsqueda de prueba en la base vectorial LanceDB (por defecto o tenant)."""
    try:
        from rag_engine import search_knowledge_base
        data = request.get_json() or {}
        query = data.get("query", "").strip()
        tema = data.get("tema") or None
        temas = data.get("temas") or None
        top_k = int(data.get("top_k", 5))
        table_name = data.get("table_name", "").strip() or None
        
        if not query:
            return jsonify({"error": "La consulta 'query' no puede estar vacía"}), 400
            
        t0 = time.time()
        results = search_knowledge_base(query=query, tema=tema, temas=temas, top_k=top_k, table_name=table_name)
        dur_ms = round((time.time() - t0) * 1000, 2)
        
        return jsonify({
            "query": query,
            "tema": tema,
            "temas": temas,
            "table_name": table_name or "teccam_knowledge_base",
            "results_count": len(results),
            "latency_ms": dur_ms,
            "results": results
        })
    except Exception as e:
        return jsonify({"error": f"Error ejecutando búsqueda RAG: {str(e)}"}), 500


@rag_bp.route("/api/rag/documents/<doc_id>", methods=["DELETE"])
def api_rag_delete_document(doc_id):
    """Elimina todos los fragmentos vectoriales de un documento específico en LanceDB."""
    try:
        from rag_engine import get_table
        table_name = request.args.get("table_name") or (request.get_json(silent=True) or {}).get("table_name") or None
        table = get_table(table_name)
        if table is None:
            return jsonify({"error": f"La tabla '{table_name or 'teccam_knowledge_base'}' no existe"}), 404
            
        clean_doc_id = doc_id.strip().replace("'", "''")
        table.delete(f"doc_id = '{clean_doc_id}'")
        
        try:
            table.create_fts_index("text", replace=True)
        except Exception:
            pass
            
        return jsonify({
            "success": True,
            "table_name": table_name or "teccam_knowledge_base",
            "deleted_doc_id": doc_id,
            "remaining_chunks": len(table)
        })
    except Exception as e:
        return jsonify({"error": f"Error al eliminar documento de LanceDB: {str(e)}"}), 500


@rag_bp.route("/api/rag/structure/<doc_id>", methods=["GET"])
def api_rag_structure(doc_id):
    """Obtiene el GPS Documental y mapa de secciones de un documento desde LanceDB."""
    try:
        from rag_engine import get_document_structure
        table_name = request.args.get("table_name") or None
        res = get_document_structure(doc_id=doc_id, table_name=table_name)
        if not res.get("success"):
            return jsonify({"error": res.get("error", "Error consultando estructura")}), 404
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": f"Error obteniendo estructura RAG: {str(e)}"}), 500


@rag_bp.route("/api/rag/library-index", methods=["GET"])
def api_rag_library_index():
    """Obtiene el Mapa Ontológico Global y árbol temático jerárquico de la biblioteca LanceDB."""
    try:
        from rag_engine import get_library_index
        solo_vigentes = request.args.get("solo_vigentes", "false").lower() in ("true", "1", "yes")
        tema = request.args.get("tema") or None
        table_name = request.args.get("table_name") or None
        res = get_library_index(solo_vigentes=solo_vigentes, tema=tema, table_name=table_name)
        if not res.get("success"):
            return jsonify({"error": res.get("error", "Error generando índice de biblioteca")}), 500
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": f"Error obteniendo índice de biblioteca: {str(e)}"}), 500
