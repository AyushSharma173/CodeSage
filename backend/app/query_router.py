# backend/app/query_router.py
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def format_graph_context(context: list[dict]) -> str:
    lines = []
    for node in context:
        node_id = node["node_id"]
        node_type = node.get("type", "unknown")
        code = node.get("code", "").strip()
        file_path = node.get("file_path", "")
        line_range = f"{node.get('start_line', '?')}–{node.get('end_line', '?')}"

        lines.append(f"--- Node {node_id} ({node_type}) ---")
        lines.append(f"File: {file_path}, Lines: {line_range}")
        if code:
            lines.append(f"Code:\n{code}")
        else:
            lines.append("Code: [Not available]")
        
        # Add relationships if present
        for rel in node.get("relationships", []):
            lines.append(f"-> {rel['type']} → Node {rel['target']}")
        lines.append("")  # blank line for spacing
    return "\n".join(lines)



def answer_query_with_llm(question: str, graph_context: list[dict]) -> str:
    """
    Calls GPT-4o with the question and graph context and returns the generated answer.
    """
    # Format the context into a readable prompt
    context_string = format_graph_context(graph_context)

    prompt = f"""You are a helpful assistant who answers user questions based on code graph context.

Context:
{context_string}

Question: {question}

Answer:"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant for reasoning about code structure."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    return response.choices[0].message.content.strip()
