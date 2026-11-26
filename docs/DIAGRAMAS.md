# Diagramas

Todos os diagramas abaixo são Mermaid e aparecem renderizados no GitHub.

## 1. Arquitetura em camadas

```mermaid
flowchart LR
    subgraph CAP["1 · Captura"]
        B["Balança com câmera de cima"]
        C["Câmeras Intelbras do salão"]
    end
    subgraph PER["2 · Percepção"]
        V["Visão do prato<br/>VLM (Gemini) + OpenCV offline"]
        Y["YOLO11n pré-treinado<br/>só contagem de pessoas"]
    end
    subgraph MOT["3 · Motor (core/)"]
        M["CMV · filas · mesas · alertas"]
    end
    DB[("SQLite na demo<br/>Supabase em produção")]
    subgraph TEL["4 · Telas e API"]
        T["Streamlit: Balança · Feedback<br/>Painel · Mesas · Comandas"]
        A["API FastAPI + webhook"]
    end
    B -->|"foto + peso + nº da comanda"| V --> M
    C --> Y --> M
    M <--> DB
    DB --> T
    DB --> A
    SaaS["Sistema de comandas existente"] -.->|"webhook (caminho C)"| A
```

## 2. Do prato à margem (fluxo da Balança)

```mermaid
sequenceDiagram
    participant Op as Operador
    participant Tela as Tela Balança
    participant Vis as Visão (VLM ou OpenCV)
    participant Cmv as core/cmv.py
    participant DB as Banco
    Op->>Tela: nº da comanda + peso + foto
    Tela->>Vis: foto do prato
    Vis-->>Tela: categorias, % de área e confiança
    alt confiança abaixo de 0,55
        Tela->>Op: pede revisão (correção em 2 s)
    end
    Tela->>Cmv: peso total + áreas
    Cmv-->>Tela: peso por categoria, custo, CMV % e margem
    Tela->>DB: salva na comanda
```

## 3. Integração sem mexer no que já funciona

```mermaid
flowchart TB
    COM["Número da comanda = chave única"]
    A["A · Conector de borda<br/>captura comanda, peso e foto na balança<br/>IMPLEMENTADO"]
    B["B · Espelho ou importação<br/>leitura somente-leitura do banco local ou CSV"]
    C["C · API e webhook<br/>aberta · item lançado · fechada<br/>endpoint simulador pronto"]
    NUC["Núcleo core/ + banco"]
    A --> COM
    B -.-> COM
    C -.-> COM
    COM --> NUC
    NUC --> OUT["Painel · Mesas · Feedback · API"]
```

A recepção humanizada e o caixa continuam exatamente como estão.
