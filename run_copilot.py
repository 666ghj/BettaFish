# run_copilot.py

import sys
import os

# Garante que o diretório do projeto está no path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from copilot.github_ingestor import GitHubIngestor
from copilot.agent_copilot import CopilotAgent

def main():
    print("🚀 BettaFish Copilot – Mirror Mode starting...")

    # 1) Coleta de dados do GitHub
    ingestor = GitHubIngestor()
    documents = ingestor.fetch_community_feedback(limit=30)

    if not documents:
        print("Nenhum documento coletado. Verifique GITHUB_TOKEN e conexão.")
        return

    # 2) Análise com LLM configurado no BettaFish
    agent = CopilotAgent(use_engine="report")  # pode mudar para "insight" ou "query"
    analysis = agent.analyze_sentiment(documents)

    # 3) Relatório final
    agent.generate_report(analysis)

if __name__ == "__main__":
    main()
