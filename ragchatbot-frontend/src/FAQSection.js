import React, { useState } from "react";
import "./styles.css";

const faqs = [
  { question: "What are incipient cable faults?", article: "Incipient cable faults are early-stage faults in electrical cables that can self-clear but indicate potential degradation. They often occur due to insulation breakdown, moisture ingress, or thermal stress." },
  { question: "How do self-clearing faults affect power quality?", article: "Self-clearing faults can cause transient disturbances, voltage sags, and flicker in the system. Over time, repeated self-clearing events can lead to permanent cable failure." },
  { question: "What are the early warning signs of cable faults?", article: "Signs include abnormal heating, intermittent voltage drops, and unexplained circuit breaker trips. Monitoring these symptoms can help prevent full-scale failure." },
  { question: "How can incipient faults be detected?", article: "Advanced techniques like Partial Discharge Analysis, Thermal Imaging, and Predictive Maintenance Algorithms are commonly used to detect incipient faults." },
];
const FAQSection = () => {
  const [selectedArticle, setSelectedArticle] = useState(null);

  return (
    <div className="faq-container">
      <h2 className="faq-header">Frequently Asked Questions</h2>
      <div className="faq-list">
        {faqs.map((faq, index) => (
          <button key={index} className="faq-item" onClick={() => setSelectedArticle(faq.article)}>
            {faq.question}
          </button>
        ))}
      </div>
      {selectedArticle && <div className="faq-article">{selectedArticle}</div>}
    </div>
  );
};


export default FAQSection;