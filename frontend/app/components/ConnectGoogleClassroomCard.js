export default function ConnectGoogleClassroomCard({
  title = "Connect Google Classroom",
  message,
}) {
  return (
    <div className="w-full max-w-2xl min-h-[220px] bg-[#444654] rounded-xl p-8 shadow-lg flex flex-col justify-center">
      <h2 className="text-2xl font-semibold mb-4">{title}</h2>

      <p className="text-gray-300 mb-6 leading-relaxed">{message}</p>

      <a
        href="/connect"
        className="w-fit bg-green-500 hover:bg-green-600 px-5 py-2 rounded-lg font-medium transition"
      >
        Go to Connect Page
      </a>
    </div>
  );
}