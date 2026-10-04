document.addEventListener(
    "DOMContentLoaded",
    () => {
        const form =
            document.getElementById(
                "aiQuestionForm"
            );

        const input =
            document.getElementById(
                "id_question"
            );

        const sendButton =
            document.getElementById(
                "aiSendButton"
            );

        const thinkingMessage =
            document.getElementById(
                "aiThinkingMessage"
            );

        const messages =
            document.getElementById(
                "aiChatMessages"
            );

        const suggestions =
            document.querySelectorAll(
                ".ai-suggestion"
            );


        function scrollToBottom() {
            if (!messages) {
                return;
            }

            messages.scrollTop =
                messages.scrollHeight;
        }


        scrollToBottom();


        suggestions.forEach(
            (button) => {
                button.addEventListener(
                    "click",
                    () => {
                        if (!input) {
                            return;
                        }

                        input.value =
                            button.dataset.question;

                        input.focus();
                    }
                );
            }
        );


        if (input) {
            input.addEventListener(
                "keydown",
                (event) => {
                    if (
                        event.key === "Enter"
                        && !event.shiftKey
                    ) {
                        event.preventDefault();

                        if (
                            input.value.trim()
                        ) {
                            form.requestSubmit();
                        }
                    }
                }
            );
        }


        if (form) {
            form.addEventListener(
                "submit",
                () => {
                    if (
                        !input
                        || !input.value.trim()
                    ) {
                        return;
                    }

                    if (sendButton) {
                        sendButton.disabled = true;
                    }

                    input.readOnly = true;

                    if (thinkingMessage) {
                        thinkingMessage.hidden = false;
                    }

                    scrollToBottom();
                }
            );
        }
    }
);