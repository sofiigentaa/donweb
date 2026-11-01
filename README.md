# Panel Caballito y Muñequita

Prototipo del sistema de asistentes para una juguetería: la muñequita (clientes) y el caballito (pedidos y stock) son la base de datos en 3D, y seis asistentes giran a su alrededor (Atención, Pedidos, Stock, Local, Seguimiento y Vendedores).

## Cómo verlo

Abrí `index.html` en el navegador. Para publicarlo, activá GitHub Pages en **Settings → Pages → Deploy from a branch → main / (root)**.

## Qué incluye

- Escena 3D interactiva: todo se puede tocar y arrastrar, y los asistentes hacen gestos.
- Tableros de la muñequita y el caballito que se abren con un toque.
- Pendientes, búsqueda y chat para pedirle cosas a los asistentes.
- Vendedores conectados por su app (simulado).
- Pantallita en vivo: stock del día con foto, precio y cantidad, y juguetes a medida con precio calculado desde la base de materiales.
- Envío por WhatsApp con el mensaje ya armado.
- Recorrido guiado ("¿Cómo se usa?") y tres idiomas (español, inglés y portugués).

## Pendiente para producción

- Los datos son de ejemplo y viven en el navegador. Hay que conectarlos a una base de datos real.
- El chat con IA funciona dentro de Claude. Fuera de Claude responde con reglas simples hasta que se agregue un servidor que llame a la API.
- WhatsApp Business API y la app de vendedores todavía no están conectadas.
