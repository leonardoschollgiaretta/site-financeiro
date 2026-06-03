@echo off
REM Sobe o site Streamlit. Duplo-clique para rodar.
REM Usa o Python do Anaconda.

cd /d "%~dp0.."
set PY="C:\Users\leonardo.giaretta\AppData\Local\anaconda3\python.exe"

echo Atualizando dados (copia dos bancos)...
%PY% "site\atualizar_dados.py"

echo.
echo Iniciando o site em http://localhost:8501
echo (Para parar: feche esta janela ou aperte Ctrl+C)
echo.
%PY% -m streamlit run "site\Home.py"

pause
