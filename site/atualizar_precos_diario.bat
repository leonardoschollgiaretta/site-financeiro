@echo off
REM ============================================================
REM Tarefa diaria: coleta o fechamento das acoes BR e copia o
REM banco atualizado para o site. Agendado para rodar as 7h.
REM (UTF-8 evita erro de emoji no console do Windows.)
REM ============================================================
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set PY="C:\Users\leonardo.giaretta\AppData\Local\anaconda3\python.exe"
set RAIZ=%~dp0..

cd /d "%RAIZ%"

echo [%date% %time%] Iniciando coleta de precos...>> "%RAIZ%\site\log_atualizacao.txt"

%PY% "financeiro\br\coletor_fechamento.py" >> "%RAIZ%\site\log_atualizacao.txt" 2>&1

echo [%date% %time%] Copiando bancos para o site...>> "%RAIZ%\site\log_atualizacao.txt"

%PY% "site\atualizar_dados.py" >> "%RAIZ%\site\log_atualizacao.txt" 2>&1

echo [%date% %time%] Concluido.>> "%RAIZ%\site\log_atualizacao.txt"
echo.>> "%RAIZ%\site\log_atualizacao.txt"
