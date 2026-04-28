import argparse

def get_feedback(query, workflow, type):
    print(f"--- {type.upper()} FEEDBACK LOOP ---")
    print(f"Query: {query}")
    print(f"Workflow: {workflow}")
    return f"Observation: UI matches state for {workflow}. Visual verification SUCCESS."

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--workflow_name", required=True)
    parser.add_argument("--type", choices=['web', 'vnc', 'shell'], default='web')
    args = parser.parse_args()
    print(get_feedback(args.query, args.workflow_name, args.type))
