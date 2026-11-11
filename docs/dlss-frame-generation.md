# DLSS Frame Generation (RecompZel)

Estado: **fase 2, primeira versão (ainda sem teste na prática)**. O jogo carrega o NVIDIA Streamline, usa o Reflex e os marcadores de latência do Streamline, marca a profundidade e os vetores de movimento do DLSS a cada frame e liga o DLSS-G. Precisa do DLSS (reescalonamento) ligado: é dele que vêm a profundidade e o movimento.

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

## Fase 2: o que o código faz

- `vk_streamline.cpp`: depois do dispositivo, acha as funções por frame (token, constantes, tags, marcadores PCL, Reflex, opções do DLSS-G). Se faltar alguma, o log diz qual e nada muda.
- `vk_reflex.cpp`: com o DLSS-G ativo, o Reflex próprio (VK_NV_low_latency2) fica de fora e os mesmos pontos do `present` mandam os marcadores ao Streamline (fim da simulação, início e fim do envio, início e fim do present, e, depois do present, o sono do Reflex e o novo token).
- `vk_temporal.cpp`: depois de cada avaliação do DLSS, a profundidade (R32F, não invertida) e o movimento (RG16F, pixels de render, rumo ao frame anterior) vão ao Streamline com as constantes da câmera (projeção, jitter, `mvecScale`, `cameraMotionIncluded`).
- Cada `present`: DLSS-G ligado (`eOn`, 1 frame gerado) se o frame tem as entradas, desligado se não (menus, carregamento).
- `vk_framegen.cpp`: a interpolação própria fica desligada enquanto o DLSS-G roda.
- Linhas do log: `Reflex and DLSS-G are on the renderer's frames now`, `DLSS-G is given the scene's depth and motion`, e a cada 300 frames `DLSS-G over the last 300 frames: ... status ... frames presented`.

## Limites conhecidos desta versão

- As matrizes entre frames são identidade (o renderer só conhece a projeção): o Streamline usa o movimento do buffer. A direção do movimento (rumo ao frame anterior) e a convenção da projeção ainda não foram confirmadas na prática.
- Sem imagem sem HUD: o DLSS-G interpola o frame final, com o HUD.
- Só RTX 40 (2x). 3x e 4x exigem RTX 50.
