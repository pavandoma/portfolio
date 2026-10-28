import { ResumeView } from "./resume-view";

export default async function ResumePage(props: PageProps<"/resumes/[id]">) {
  const { id } = await props.params;
  return <ResumeView id={id} />;
}
