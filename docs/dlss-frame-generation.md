# DLSS Frame Generation (RecompZel)

Estado: **fase 1**. O jogo carrega o NVIDIA Streamline e diz no log se a sua placa roda DLSS-G. Ainda **não gera frames**.

O código (`gpu/vk/vk_streamline.cpp`) foi escrito a partir dos guias públicos da NVIDIA (Streamline, licença MIT). Nenhum código de
outro projeto foi copiado.

## Como testar (placas RTX 40 e 50)

1. As DLLs da NVIDIA ficam na pasta `streamline` ao lado do jogo (ou na pasta do jogo): `sl.interposer.dll`, `sl.common.dll`,
   `sl.dlss_g.dll`, `sl.pcl.dll`, `sl.reflex.dll` e `nvngx_dlssg.dll`, versão 2.14.16. Elas **não** fazem parte deste repositório:
   a `nvngx_dlssg.dll` usa a NVIDIA RTX SDKs License (só para placas NVIDIA). Baixe-as do Streamline oficial
   (https://github.com/NVIDIA-RTX/Streamline).
2. Crie `hookshot_env.txt` na pasta do jogo com a linha `RX_VK_DLSSG=1`.
3. Abra o jogo e feche. No `hookshot_log.txt` procure as linhas que começam com `streamline:`.

Sem `RX_VK_DLSSG=1` nada disto roda e o jogo se comporta como antes.

## O que o log pode dizer

| Linha | Significado |
|---|---|
| `streamline: started from ... (2.14.16)` | O interposer carregou e o Streamline iniciou |
| `streamline: DLSS-G is supported on this GPU` | A placa e o driver rodam DLSS-G |
| `DLSS-G state: ... up to N generated frames` | Quantos frames ele gera entre dois renderizados (0: ainda não informou) |
| `does not run on this GPU or driver` | Placa abaixo da RTX 40, driver antigo ou agendamento de GPU acelerado por hardware desligado |

## Fase 2 (a fazer)

Marcar profundidade e vetores de movimento a cada frame (o renderer já os tem para o FSR 3.1, `vk_fsr3_inputs.cpp`), enviar a
câmera, usar o Reflex do Streamline em vez do `vk_reflex.cpp`, ligar o DLSS-G e deixar o Streamline inserir os frames no
`present` (o `vk_framegen.cpp` não gera frame próprio enquanto o DLSS-G roda).
