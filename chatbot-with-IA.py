import sys
import os
import speech_recognition as sr
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QPushButton, QVBoxLayout,
    QWidget, QLabel, QHBoxLayout, QFileDialog, QToolTip, QMessageBox,
    QFrame, QScrollArea, QDialog, QDialogButtonBox, QCheckBox
)
from PyQt5.QtGui import QIcon, QPixmap, QFont, QPainter, QColor, QFontDatabase
from PyQt5.QtCore import Qt, pyqtSignal, QRect, QTimer
import pyttsx3
from PIL import Image
import pytesseract
import google.generativeai as genai

key = 'SUA_API_KEY_AQUI'
genai.configure(api_key=key)

modelo = genai.GenerativeModel('gemini-1.0-pro')
chat = modelo.start_chat(history=[])

engine = pyttsx3.init()


class EnterTextEdit(QTextEdit):
    enterPressed = pyqtSignal()

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        if event.key() == Qt.Key_Return:
            self.enterPressed.emit()


class ChatBubble(QWidget):
    def __init__(self, mensagem, is_user=True, fixed_size=False):
        super().__init__()
        self.mensagem = mensagem
        self.is_user = is_user
        self.fixed_size = fixed_size

        self.setup_ui()

    def setup_ui(self):
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(15, 10, 15, 10)
        self.setLayout(self.layout)

        self.mensagem_label = QLabel(self.mensagem)
        self.mensagem_label.setWordWrap(True)
        self.mensagem_label.setStyleSheet("font-size: 14px;")

        if self.is_user:
            self.setStyleSheet(
                "background-color: #DCF8C6; border-radius: 20px; border: 1px solid #B3DF86; padding: 15px;"
            )
            self.mensagem_label.setAlignment(Qt.AlignRight)
        else:
            self.setStyleSheet(
                "background-color: #E8E8E8; border-radius: 20px; border: 1px solid #ccc; padding: 15px;"
            )
            self.mensagem_label.setAlignment(Qt.AlignLeft)

        if not self.fixed_size:
            font_size = 12 + len(self.mensagem) // 30
            if font_size < 8:
                font_size = 8
            self.mensagem_label.setStyleSheet(f"font-size: {font_size}px;")

        self.layout.addWidget(self.mensagem_label)


class AudioScrollBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.audio_on = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)


        if self.audio_on:
            painter.setBrush(QColor("#00FF00"))
        else:
            painter.setBrush(QColor("#808080"))

        # Desenhar o retângulo
        rect = QRect(0, 0, self.width(), self.height())
        painter.drawRect(rect)

    def set_audio_state(self, state):
        self.audio_on = state
        self.update()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Chat com IA - Gemini")

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self.title_layout = QHBoxLayout()
        self.layout.addLayout(self.title_layout)

        self.title_label = QLabel("Bem-vindo ao Chatbot com IA - Gemini")
        font = QFont("Arial", 16, QFont.Bold)
        self.title_label.setFont(font)
        self.title_label.setStyleSheet("background-color: #003FA3; color: white;")
        self.title_label.setFixedHeight(60)
        self.title_label.setAlignment(Qt.AlignCenter)

        self.audio_checkbox = QCheckBox("Reproduzir Áudio")
        self.audio_checkbox.setStyleSheet(
            "QCheckBox { color: white; font-size: 14px; }"
            "QCheckBox::indicator { width: 15px; height: 15px; }"
            "QCheckBox::indicator:unchecked { background-color: #003FA3; border: 2px solid white; }"
            "QCheckBox::indicator:checked { background-color: #00FF00; border: 2px solid white; }"
            "QCheckBox::indicator:checked:hover { background-color: #00CC00; }"
        )
        self.audio_checkbox.clicked.connect(self.toggle_audio)

        self.title_layout.addWidget(self.title_label, alignment=Qt.AlignCenter)
        self.title_layout.addWidget(self.audio_checkbox, alignment=Qt.AlignRight)

        self.central_widget.setStyleSheet("background-color: #003FA3;")

        self.chat_history = QVBoxLayout()  # Layout agora é QVBoxLayout
        self.chat_history_frame = QFrame()
        self.chat_history_frame.setLayout(self.chat_history)
        self.chat_history_frame.setFrameShape(QFrame.NoFrame)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.chat_history_frame)
        self.layout.addWidget(self.scroll_area)

        self.input_layout = QHBoxLayout()
        self.layout.addLayout(self.input_layout)

        self.prompt_entry = EnterTextEdit()
        self.prompt_entry.setStyleSheet(
            "font: 12pt Helvetica; border: 2px solid black; border-radius: 10px; padding: 10px; background-color: #ffffff;"
        )
        self.prompt_entry.setFixedHeight(60)
        self.input_layout.addWidget(self.prompt_entry)
        self.prompt_entry.enterPressed.connect(self.enviar_mensagem)

        self.send_button = QPushButton()
        self.send_button.setIcon(
            QIcon(QPixmap("send_icon.png")))
        self.send_button.setStyleSheet(
            "background-color: green; color: white; border: 1px solid black; padding: 20px 20px; border-radius: 10px;")
        self.send_button.clicked.connect(self.enviar_mensagem)
        self.input_layout.addWidget(self.send_button)
        QToolTip.setFont(QFont('Arial', 10))
        self.send_button.setToolTip("<font color='black'>Enviar</font>")

        self.image_button = QPushButton()
        self.image_button.setIcon(
            QIcon(QPixmap("upload.png")))
        self.image_button.setStyleSheet(
            "background-color: #0084ff; color: white; border: 1px solid black; padding: 20px 20px; border-radius: 10px;")
        self.image_button.clicked.connect(self.carregar_imagem)
        self.input_layout.addWidget(self.image_button)
        QToolTip.setFont(QFont('Arial', 10))
        self.image_button.setToolTip("<font color='black'>Carregar imagem</font>")

        self.audio_button = QPushButton("Gravar Áudio")
        self.audio_button.setStyleSheet(
            "background-color: #007ACC; color: white; border: 1px solid black; padding: 20px 20px; border-radius: 10px;")
        self.audio_button.clicked.connect(self.gravar_audio)
        self.input_layout.addWidget(self.audio_button)
        self.audio_button.setToolTip("<font color='black'>Gravar Áudio</font>")

        self.clear_button = QPushButton("Limpar Chat")
        self.clear_button.setStyleSheet(
            "background-color: #CC0000; color: white; border: 1px solid black; padding: 10px 20px; border-radius: 10px; font-weight: bold;"
        )
        self.clear_button.clicked.connect(self.confirmar_limpar_chat)
        self.layout.addWidget(self.clear_button)

        # Barra de rolagem de áudio
        self.audio_scrollbar = AudioScrollBar()
        self.layout.addWidget(self.audio_scrollbar)

        # Conectar o pressionamento da tecla Enter ao envio de mensagens
        self.prompt_entry.enterPressed.connect(self.enviar_mensagem)
        QToolTip.setFont(QFont('Arial', 10))
        self.clear_button.setToolTip("<font color='black'>Limpar Chat</font>")

        self.audio_playing = False
        self.audio_file_path = None

        self.recognizer = sr.Recognizer()

    def confirmar_limpar_chat(self):
        dialog = QMessageBox()
        dialog.setIcon(QMessageBox.Question)
        dialog.setText("Tem certeza de que deseja limpar o chat?")
        dialog.setWindowTitle("Limpar Chat")
        dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        dialog.buttonClicked.connect(self.limpar_chat_dialog)
        dialog.exec_()

    def limpar_chat_dialog(self, button):
        if button.text() == "&Yes":
            self.limpar_chat()

    def enviar_mensagem(self):
        mensagem_usuario = self.prompt_entry.toPlainText().strip()
        if mensagem_usuario:
            self.adicionar_mensagem(mensagem_usuario, is_user=True)
            resposta = chat.send_message(mensagem_usuario)
            self.adicionar_mensagem(resposta.text)
            if self.audio_playing:
                engine.say(resposta.text)
                engine.runAndWait()
            self.prompt_entry.clear()

    def limpar_chat(self):
        for i in reversed(range(self.chat_history.count())):
            self.chat_history.itemAt(i).widget().setParent(None)

    def gravar_audio(self):
        self.audio_button.setEnabled(False)
        self.audio_button.setText("Gravando...")
        QTimer.singleShot(3000, self.stop_gravacao)
        self.audio_data = b''
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source)
            self.audio_data = self.recognizer.listen(source)

    def stop_gravacao(self):
        self.audio_button.setEnabled(True)
        self.audio_button.setText("Gravar Áudio")

        try:
            texto_transcrito = self.recognizer.recognize_google(self.audio_data, language='pt-BR')
            self.adicionar_mensagem(texto_transcrito, is_user=True)
            resposta = chat.send_message(texto_transcrito)
            self.adicionar_mensagem(resposta.text)
            if self.audio_playing:
                engine.say(resposta.text)
                engine.runAndWait()
        except sr.UnknownValueError:
            self.adicionar_mensagem("Não entendi o que foi dito.")
        except sr.RequestError as e:
            self.adicionar_mensagem(f"Erro ao transcrever áudio: {e}")

    def carregar_imagem(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'Open File', '', 'Image files (*.jpg *.png)')
        if filename:
            imagem = Image.open(filename)
            texto_imagem = pytesseract.image_to_string(imagem)
            self.adicionar_mensagem(texto_imagem, is_user=True)

    def adicionar_mensagem(self, mensagem, is_user=False):
        bubble = ChatBubble(mensagem, is_user)
        self.chat_history.addWidget(bubble, alignment=Qt.AlignRight if is_user else Qt.AlignLeft)

    def toggle_audio(self, state):
        self.audio_playing = state
        if self.audio_playing:
            self.audio_scrollbar.set_audio_state(True)
        else:
            self.audio_scrollbar.set_audio_state(False)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.setGeometry(100, 100, 1000, 900)
    window.show()
    sys.exit(app.exec_())