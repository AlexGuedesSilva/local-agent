import logging
import os

from agent.core.agent import Agent


def _confirm_action(description: str) -> bool:
    print(f"\nAção que altera arquivos: {description}")
    answer = input("Confirma esta movimentação? Digite 's' para confirmar [s/N]: ")
    return answer.strip().casefold() in {"s", "sim"}


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOCAL_AGENT_LOG_LEVEL", "WARNING").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    agent = Agent(confirm_action=_confirm_action)

    print("=================================")
    print("       LOCAL AI AGENT")
    print("=================================")
    print("Digite 'sair' para encerrar.\n")

    while True:
        user_input = input("Você: ")
        if user_input.lower() == "sair":
            print("Encerrando...")
            break

        response = agent.run(user_input)
        print(f"\nAgente: {response}\n")


if __name__ == "__main__":
    main()
