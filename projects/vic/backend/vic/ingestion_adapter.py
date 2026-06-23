from typing import Any, Dict, List


class IngestionAdapter:
    """
    Deterministic ingestion layer.

    Converts raw multi-session chat/history JSON into IR.

    Output is STRICTLY:
        { "intents": [ ... ] }

    No inference. Only schema-based translation.
    """

    def ingest(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        sessions = raw.get("sessions", [])

        intents: List[Dict[str, Any]] = []

        for session in sessions:
            session_id = session.get("session_id")
            messages = session.get("messages", [])

            for idx, msg in enumerate(messages):
                msg_type = msg.get("type")

                provenance = {
                    "session_id": session_id,
                    "message_index": idx,
                    "timestamp": msg.get("timestamp"),
                    "source": "ingestion_adapter"
                }

                if msg_type in ("ADD_NODE", "node_create"):
                    node = msg.get("node", {})

                    intents.append({
                        "op": "ADD_NODE",
                        "node": {
                            "entity_id": node.get("entity_id"),
                            "type": node.get("type")
                        },
                        "provenance": provenance
                    })

                elif msg_type in ("ADD_EDGE", "edge_create"):
                    intents.append({
                        "op": "ADD_EDGE",
                        "from": msg.get("from"),
                        "to": msg.get("to"),
                        "relation": msg.get("relation"),
                        "provenance": provenance
                    })

                else:
                    continue

        return {"intents": intents}
