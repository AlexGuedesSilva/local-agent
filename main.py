import logging

from agent.config import ConfigurationError, Settings
from agent.core.agent import Agent
from agent.core.history import ConversationHistory


def _confirm_action(description: str) -> bool:
    print(f"\nAção que requer confirmação:\n{description}")
    answer = input("Confirma esta ação? Digite 's' para confirmar [s/N]: ")
    return answer.strip().casefold() in {"s", "sim"}


def main() -> None:
    try:
        settings = Settings.from_env()
    except ConfigurationError as error:
        print(f"Configuração inválida: {error}")
        return
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    agent = Agent(confirm_action=_confirm_action, settings=settings)
    history_store = ConversationHistory()
    conversation_id = history_store.latest_conversation_id()
    if conversation_id is None:
        conversation_id = history_store.create_conversation()
    history = history_store.load_messages(conversation_id)
    summary, summary_message_count = history_store.load_context_summary(conversation_id)

    print("=================================")
    print("       LOCAL AI AGENT")
    print("=================================")
    print(f"Histórico local: {history_store.database_path}")
    print("Comandos: /nova, /conversas, /abrir ID, /limpar, /apagar ID, /apagar-tudo, sair\n")

    while True:
        user_input = input("Você: ")
        command = user_input.strip()
        if command.casefold() in {"sair", "/sair", "exit", "quit"}:
            print("Encerrando...")
            break

        if command.casefold() == "/nova":
            conversation_id = history_store.create_conversation()
            history = []
            summary = ""
            summary_message_count = 0
            print(f"Nova conversa iniciada ({conversation_id}).\n")
            continue

        if command.casefold() == "/conversas":
            conversations = history_store.list_conversations()
            if not conversations:
                print("Nenhuma conversa salva.\n")
                continue
            for conversation in conversations:
                active = " (atual)" if conversation.conversation_id == conversation_id else ""
                print(
                    f"{conversation.conversation_id}{active} | {conversation.title} | "
                    f"{conversation.updated_at}"
                )
            print()
            continue

        if command.casefold().startswith("/abrir "):
            requested_id = command[7:].strip()
            if not requested_id or not history_store.has_conversation(requested_id):
                print("Conversa não encontrada. Use /conversas para ver os IDs salvos.\n")
                continue
            conversation_id = requested_id
            history = history_store.load_messages(conversation_id)
            summary, summary_message_count = history_store.load_context_summary(conversation_id)
            print(f"Conversa {conversation_id} carregada.\n")
            continue

        if command.casefold() == "/limpar":
            history_store.clear_messages(conversation_id)
            history = []
            summary = ""
            summary_message_count = 0
            print("Mensagens da conversa atual apagadas.\n")
            continue

        if command.casefold().startswith("/apagar "):
            requested_id = command[8:].strip()
            if not requested_id or not history_store.delete_conversation(requested_id):
                print("Conversa não encontrada. Use /conversas para ver os IDs salvos.\n")
                continue
            if requested_id == conversation_id:
                conversation_id = history_store.create_conversation()
                history = []
                summary = ""
                summary_message_count = 0
            print(f"Conversa {requested_id} apagada.\n")
            continue

        if command.casefold() == "/apagar-tudo":
            answer = input("Apagar todas as conversas salvas? Digite 's' para confirmar [s/N]: ")
            if answer.strip().casefold() not in {"s", "sim"}:
                print("Ação cancelada.\n")
                continue
            removed = history_store.delete_all_conversations()
            conversation_id = history_store.create_conversation()
            history = []
            summary = ""
            summary_message_count = 0
            print(f"Histórico apagado ({removed} conversa(s)).\n")
            continue

        is_first_message = not history
        response = agent.run(
            user_input, history=history, summary=summary,
            summary_message_count=summary_message_count,
        )
        summary = agent.last_summary
        summary_message_count = agent.last_summary_message_count
        history_store.save_messages(
            conversation_id,
            history,
            title=user_input.strip().replace("\n", " ")[:80] if is_first_message else None,
        )
        history_store.save_summary(conversation_id, summary, summary_message_count)
        print(f"\nAgente: {response}\n")


if __name__ == "__main__":
    main()
