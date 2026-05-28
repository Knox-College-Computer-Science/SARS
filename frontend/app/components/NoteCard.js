export default function NoteCard({ note, isPreviewOpen, onPreviewToggle }) {
  return (
    <div className="group bg-surface-container border border-outline-variant/30 hover:border-primary/50 rounded-lg transition-all duration-200 hover:bg-surface-container-high">
      <div className="p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        {/* Icon + Info */}
        <div className="flex items-center gap-4 flex-1 min-w-0">
          <div className="w-10 h-10 rounded-lg bg-red-900/20 text-red-400 flex items-center justify-center flex-shrink-0">
            <span className="material-symbols-outlined" style={{ fontSize: 22 }}>picture_as_pdf</span>
          </div>
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-on-surface group-hover:text-primary transition-colors truncate">
              {note.filename}
            </h3>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1">
              {note.subject && (
                <span className="text-[10px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded uppercase tracking-wider">
                  {note.subject}
                </span>
              )}
              {note.upload_time && (
                <span className="text-xs text-on-surface-variant flex items-center gap-1">
                  <span className="material-symbols-outlined" style={{ fontSize: 13 }}>calendar_today</span>
                  {note.upload_time}
                </span>
              )}
              {note.uploaded_by && (
                <span className="text-xs text-on-surface-variant flex items-center gap-1">
                  <span className="material-symbols-outlined" style={{ fontSize: 13 }}>person</span>
                  {note.uploaded_by}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={onPreviewToggle}
            className={`px-4 py-1.5 text-xs font-bold rounded-lg border transition-all ${
              isPreviewOpen
                ? "bg-primary text-on-primary border-primary"
                : "text-primary bg-primary/10 border-primary/20 hover:bg-primary hover:text-on-primary"
            }`}
          >
            {isPreviewOpen ? "Close" : "Preview"}
          </button>
          <a
            href={note.drive_view_link || `/api/files/${note.filename}`}
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-1.5 text-xs font-bold text-on-surface-variant bg-surface-container-highest rounded-lg hover:bg-outline-variant transition-all flex items-center gap-1"
          >
            Open
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>open_in_new</span>
          </a>
        </div>
      </div>

      {/* Inline PDF preview */}
      {isPreviewOpen && (
        <div className="border-t border-outline-variant overflow-hidden rounded-b-lg">
          <iframe
            src={
              note.drive_file_id
                ? `https://drive.google.com/file/d/${note.drive_file_id}/preview`
                : `/api/files/${note.filename}`
            }
            title={note.filename}
            className="w-full"
            style={{ height: 520, border: "none" }}
          />
        </div>
      )}
    </div>
  );
}