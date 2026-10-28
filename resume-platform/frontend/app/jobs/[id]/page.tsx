import { JobView } from "./job-view";

export default async function JobPage(props: PageProps<"/jobs/[id]">) {
  const { id } = await props.params;
  const search = await props.searchParams;
  return <JobView id={id} duplicate={search.duplicate === "1"} />;
}
