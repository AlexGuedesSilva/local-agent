from agent.core.agent import Agent


def main() -> None:
    agent = Agent()

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
