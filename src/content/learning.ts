/**
 * The learning path. Edit this file to change what is tracked; ticking items
 * off happens on the page itself (see src/components/learning/).
 *
 * Item ids are the keys progress is saved under, so renaming an id loses its
 * tick — change titles freely, change ids only on purpose. Hours are an honest
 * estimate and only feed the "hours done" figure.
 */

export type LearningItem = { id: string; title: string; hours: number };
export type LearningModule = { id: string; title: string; items: LearningItem[] };
export type LearningTrack = {
  id: string;
  title: string;
  summary: string;
  modules: LearningModule[];
};

export const learning = {
  label: "Learning log",
  title: "What I am learning, and how far along it is.",
  intro:
    "The path I am working through, with every step ticked off as it is finished. Nothing here is a claim — it is a record.",
  tracks: [
    {
      id: "foundations",
      title: "Foundations",
      summary: "The mathematics and Python that everything else rests on.",
      modules: [
        {
          id: "python-data",
          title: "Python for data",
          items: [
            { id: "numpy-pandas", title: "NumPy and pandas, without tutorials", hours: 12 },
            { id: "plotting", title: "Plotting that explains, not decorates", hours: 5 },
            { id: "testing-python", title: "Testing data code with pytest", hours: 6 },
          ],
        },
        {
          id: "maths",
          title: "Mathematics",
          items: [
            { id: "linear-algebra", title: "Linear algebra: vectors, matrices, decompositions", hours: 20 },
            { id: "probability", title: "Probability and distributions", hours: 16 },
            { id: "calculus-gradients", title: "Calculus and gradients by hand", hours: 10 },
          ],
        },
      ],
    },
    {
      id: "machine-learning",
      title: "Machine learning",
      summary: "Classical methods and, above all, how to tell if they work.",
      modules: [
        {
          id: "supervised",
          title: "Supervised learning",
          items: [
            { id: "regression-classification", title: "Regression and classification from scratch", hours: 14 },
            { id: "trees-ensembles", title: "Trees, forests and gradient boosting", hours: 12 },
            { id: "feature-engineering", title: "Feature engineering and leakage", hours: 8 },
          ],
        },
        {
          id: "evaluation",
          title: "Evaluation",
          items: [
            { id: "metrics", title: "Metrics that match the problem", hours: 6 },
            { id: "validation", title: "Cross-validation and honest splits", hours: 6 },
            { id: "error-analysis", title: "Error analysis as a habit", hours: 5 },
          ],
        },
      ],
    },
    {
      id: "deep-learning",
      title: "Deep learning",
      summary: "Networks, trained and understood.",
      modules: [
        {
          id: "pytorch",
          title: "PyTorch",
          items: [
            { id: "autograd-training-loop", title: "Autograd and a training loop from nothing", hours: 10 },
            { id: "cnn-vision", title: "Convolutional networks for vision", hours: 14 },
            { id: "regularisation", title: "Regularisation and optimisation", hours: 8 },
          ],
        },
        {
          id: "transformers",
          title: "Transformers",
          items: [
            { id: "attention", title: "Attention, implemented", hours: 10 },
            { id: "tiny-gpt", title: "Build and train a tiny GPT", hours: 18 },
            { id: "fine-tuning", title: "Fine-tuning and parameter-efficient methods", hours: 12 },
          ],
        },
      ],
    },
    {
      id: "llm-systems",
      title: "LLM systems",
      summary: "Making language models dependable inside real products.",
      modules: [
        {
          id: "retrieval",
          title: "Retrieval",
          items: [
            { id: "embeddings-vector-search", title: "Embeddings and vector search", hours: 8 },
            { id: "rag-pipeline", title: "A RAG pipeline, end to end", hours: 14 },
            { id: "chunking-reranking", title: "Chunking, hybrid search and reranking", hours: 10 },
          ],
        },
        {
          id: "llm-evaluation",
          title: "Evaluation and agents",
          items: [
            { id: "eval-harness", title: "A versioned evaluation harness", hours: 12 },
            { id: "llm-judges", title: "LLM judges and their failure modes", hours: 6 },
            { id: "tool-use-agents", title: "Tool use and agent loops", hours: 12 },
          ],
        },
      ],
    },
    {
      id: "mlops",
      title: "MLOps",
      summary: "Shipping it, watching it, keeping it honest.",
      modules: [
        {
          id: "shipping",
          title: "Shipping",
          items: [
            { id: "docker", title: "Containers with Docker", hours: 6 },
            { id: "serving-apis", title: "Serving models behind an API", hours: 8 },
            { id: "ci-cd", title: "CI/CD for ML code", hours: 6 },
          ],
        },
        {
          id: "operating",
          title: "Operating",
          items: [
            { id: "monitoring-drift", title: "Monitoring and drift detection", hours: 8 },
            { id: "latency-cost", title: "Latency and cost budgets", hours: 6 },
            { id: "experiment-tracking", title: "Experiment tracking and reproducibility", hours: 6 },
          ],
        },
      ],
    },
  ] satisfies LearningTrack[],
};

export const allItems = learning.tracks.flatMap((track) =>
  track.modules.flatMap((module) =>
    module.items.map((item) => ({ ...item, trackId: track.id, moduleId: module.id })),
  ),
);
