# Guard final capacity read

The previous Seeder attempt exposed a failure in the finalizer. A second Docker timeout escaped the final capacity read before the guard recorded the failed result or finalized the scheduler request.

The staged patch records missing capacity explicitly and marks the run failed. It then executes the existing ownership decision. Confirmed stopped work releases its reservation and retains a failure receipt. Uncertain ownership keeps the reservation and writes a retained failure receipt. The outer command still reports the capacity error.

The isolated test runs both the installed and candidate engine code against private scheduler directories. A real child exits after writing its own marker and the capacity provider then throws. The stock engine leaves the request running. The candidate finishes the request when stop is confirmed and retains it when the supplied container observation is uncertain. The Docker observations in this fixture are injected. This verifies the terminal exception path and leaves the installed engine untouched.

The patch does not resolve Docker volume timeouts during an application build. The real-owner lifecycle and browser gates remain open.
