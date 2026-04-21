export default function NoteCard({ name, subject }) {
  return (
    <div style={{ border: "1px solid black", padding: "10px", margin: "10px" }}>
      <h3>{name}</h3>
      <p>{subject}</p>
    </div>
  );
}