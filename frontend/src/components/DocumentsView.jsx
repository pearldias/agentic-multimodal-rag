import { useState, useMemo, useRef } from "react";

const DEFAULT_DOCUMENTS = [
  { name: "SYN_001_Company_Overview_Services.pdf", type: "PDF", category: "Company Overview", status: "Indexed & Active", source: "data/raw" },
  { name: "SYN_002_Employee_Handbook.pdf", type: "PDF", category: "HR Policy", status: "Indexed & Active", source: "data/raw" },
  { name: "SYN_003_Leave_WFH_Policy.pdf", type: "PDF", category: "HR Policy", status: "Indexed & Active", source: "data/raw" },
  { name: "SYN_004_Employee_Onboarding_Guide.docx", type: "DOCX", category: "HR Policy", status: "Indexed & Active", source: "data/raw" },
  { name: "SYN_005_IT_Support_Access_Guide.pdf", type: "PDF", category: "IT Support", status: "Indexed & Active", source: "data/raw" },
  { name: "SYN_006_Project_Delivery_SOP.docx", type: "DOCX", category: "Operations", status: "Indexed & Active", source: "data/raw" },
  { name: "SYN_007_Requirements_Engineering_Guide.docx", type: "DOCX", category: "Engineering", status: "Indexed & Active", source: "data/raw" },
  { name: "SYN_008_Software_Development_Standards.docx", type: "DOCX", category: "Engineering", status: "Indexed & Active", source: "data/raw" },
  { name: "SYN_009_Testing_Quality_Engineering.pdf", type: "PDF", category: "Quality Assurance", status: "Indexed & Active", source: "data/raw" },
  { name: "SYN_010_Deployment_Release_Management.pdf", type: "PDF", category: "DevOps", status: "Indexed & Active", source: "data/raw" },
  { name: "SYN_011_Proposal_RFP_Guidelines.docx", type: "DOCX", category: "Operations", status: "Indexed & Active", source: "data/raw" },
  { name: "SYN_012_Solution_Architecture_Guidelines.pdf", type: "PDF", category: "Architecture", status: "Indexed & Active", source: "data/raw" },
  { name: "SYN_013_Technology_Capability_Catalogue.pdf", type: "PDF", category: "Capabilities", status: "Indexed & Active", source: "data/raw" },
  { name: "SYN_014_Cybersecurity_Policy_Secure_Dev.pdf", type: "PDF", category: "Security", status: "Indexed & Active", source: "data/raw" },
  { name: "SYN_014_Employee_Skills_Directory.xlsx", type: "XLSX", category: "Learning", status: "Indexed & Active", source: "data/raw" },
  { name: "SYN_015_Data_Protection_Privacy.pdf", type: "PDF", category: "Security", status: "Indexed & Active", source: "data/raw" },
  { name: "SYN_016_AI_RAG_Development_Guide.pdf", type: "PDF", category: "Engineering", status: "Indexed & Active", source: "data/raw" },
  { name: "SYN_017_Training_Upskilling_Catalogue.pdf", type: "PDF", category: "Learning", status: "Indexed & Active", source: "data/raw" },
  { name: "SYN_018_Training_Course_Catalogue.xlsx", type: "XLSX", category: "Learning", status: "Indexed & Active", source: "data/raw" },
  { name: "SYN_019_Project_POC_Catalogue.xlsx", type: "XLSX", category: "Operations", status: "Indexed & Active", source: "data/raw" },
  { name: "SYN_020_Tech_Service_Mapping.xlsx", type: "XLSX", category: "Architecture", status: "Indexed & Active", source: "data/raw" },
];

export default function DocumentsView({
  documents = [],
  onAskQuestion,
  onUploadFile,
  uploading = false,
}) {
  const [searchTerm, setSearchTerm] = useState("");
  const [filterType, setFilterType] = useState("ALL");
  const fileInputRef = useRef(null);

  const activeDocList = documents && documents.length > 0 ? documents : DEFAULT_DOCUMENTS;

  const filteredDocs = useMemo(() => {
    return activeDocList.filter((doc) => {
      const matchesSearch =
        doc.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (doc.category && doc.category.toLowerCase().includes(searchTerm.toLowerCase()));
      const matchesType = filterType === "ALL" || doc.type === filterType;
      return matchesSearch && matchesType;
    });
  }, [activeDocList, searchTerm, filterType]);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0] && onUploadFile) {
      onUploadFile(e.target.files[0]);
      e.target.value = "";
    }
  };

  const getTypeBadgeClass = (type) => {
    switch (type) {
      case "PDF":
        return "badge-pdf";
      case "DOCX":
        return "badge-docx";
      case "XLSX":
        return "badge-xlsx";
      default:
        return "badge-generic";
    }
  };

  return (
    <div className="documents-page" aria-label="Knowledge base documents">
      {/* Hidden File Input */}
      <input
        type="file"
        ref={fileInputRef}
        accept=".pdf,.docx,.xlsx,.txt"
        style={{ display: "none" }}
        onChange={handleFileChange}
      />

      <div className="doc-page-header">
        <div className="doc-page-header-top">
          <div className="doc-page-title-group">
            <h2>Knowledge Base</h2>
            <span className="doc-count-pill">{activeDocList.length} documents indexed</span>
          </div>

          <button
            type="button"
            className={`primary-upload-btn ${uploading ? "uploading-active" : ""}`}
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            aria-label="Upload document"
          >
            {uploading ? (
              <>
                <div className="upload-spinner-sm" aria-hidden="true" />
                <span>Indexing Document...</span>
              </>
            ) : (
              <>
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  width="16"
                  height="16"
                  aria-hidden="true"
                >
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
                <span>Upload Document</span>
              </>
            )}
          </button>
        </div>

        <p className="doc-page-description">
          These documents are chunked and indexed in ChromaDB using Gemini embeddings.
          The RAG assistant queries this vector index in real-time to answer your questions with citations.
        </p>
      </div>

      {/* Filter and Search Bar */}
      <div className="doc-controls">
        <div className="doc-search-box">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            width="16"
            height="16"
            aria-hidden="true"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            placeholder="Search documents by name or category..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            aria-label="Search documents"
          />
        </div>

        <div className="doc-type-filters">
          {["ALL", "PDF", "DOCX", "XLSX", "TXT"].map((type) => (
            <button
              key={type}
              type="button"
              className={`filter-btn ${filterType === type ? "active" : ""}`}
              onClick={() => setFilterType(type)}
            >
              {type}
            </button>
          ))}
        </div>
      </div>

      {/* Documents Table */}
      <div className="doc-table-container">
        <table className="doc-table" aria-label="Document index table">
          <thead>
            <tr>
              <th scope="col">Document Name</th>
              <th scope="col">Category</th>
              <th scope="col">File Type</th>
              <th scope="col">Status</th>
              <th scope="col">Source Path</th>
              <th scope="col" className="text-right">Action</th>
            </tr>
          </thead>
          <tbody>
            {filteredDocs.map((doc, idx) => (
              <tr key={idx}>
                <td className="doc-name-cell">
                  <div className="doc-name-wrapper">
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      width="16"
                      height="16"
                      className="doc-icon-svg"
                      aria-hidden="true"
                    >
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                    </svg>
                    <span className="doc-filename" title={doc.name}>
                      {doc.name}
                    </span>
                  </div>
                </td>
                <td>
                  <span className="doc-category-badge">{doc.category}</span>
                </td>
                <td>
                  <span className={`doc-type-badge ${getTypeBadgeClass(doc.type)}`}>
                    {doc.type}
                  </span>
                </td>
                <td>
                  <span className="doc-status-badge">
                    <span className="status-dot-sm" />
                    {doc.status}
                  </span>
                </td>
                <td className="doc-source-cell">
                  <code>{doc.source}</code>
                </td>
                <td className="text-right">
                  <button
                    type="button"
                    className="ask-doc-btn"
                    onClick={() => onAskQuestion(`What information is covered in ${doc.name}?`)}
                    title={`Ask a question about ${doc.name}`}
                  >
                    Query
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {filteredDocs.length === 0 && (
          <div className="empty-docs-state">
            <p>No documents matched your search query.</p>
          </div>
        )}
      </div>
    </div>
  );
}
