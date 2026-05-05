import subprocess

def run_rivet_workflows(graph_name: str, client_id: str | None = None):
    print(f"Starting Rivet orchestration for '{graph_name}' via Node.js...")
    cmd = ["node", "run_workflows.js", graph_name]
    if client_id:
        cmd.append(client_id)
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    
    if result.returncode != 0:
        print(f"Error executing Rivet workflow {graph_name}:")
        print(result.stderr)
        print(result.stdout)
        return False
    
    print(result.stdout)
    return True
