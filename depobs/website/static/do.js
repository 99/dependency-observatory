async function startScan(args) {
  let scanURI = "/api/v1/scans";
  let body = {
    name: "scan_score_npm_package",
    args: [args["package_name"], args["package_version"]],
  };
  if (!args["package_version"]) {
    console.debug("removing version arg for falsy package_version");
    body.args = [args["package_name"]];
  }
  console.debug("starting scan with req body:", body);

  let response = await fetch(scanURI, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  }).catch((err) => {
    console.error(`error POSTing to ${scanURI}: ${err}`);
    throw err;
  });
  if (response.status !== 202) {
    let err = new Error(`${response.status} from ${scanURI}`);
    err.response = response;
    throw err;
  }
  console.log("start scan response: ", response);
  let responseJSON = await response.json();

  console.log("start scan response JSON: ", responseJSON);
  return responseJSON;
}

async function checkReportExists(formData) {
  // check for a package report
  let queryParams = new URLSearchParams(formData);
  let reportURI = `/package_report?${queryParams}`;
  let response = await fetch(reportURI, {
    method: "HEAD",
  });
  return response;
}

// view / UI code

const formEl = document.getElementById("search-form");
const formFieldsetEls = formEl.querySelectorAll("fieldset");

function updateSearchError(err, errContextMessage) {
  // takes an Error with an optional .response property set and
  // displays errContextMessage
  const errorEl = document.getElementById("search-error");
  const errorContextMessageEl = document.getElementById("error-context");
  const errorReqIDEl = document.getElementById("error-request-id");
  const errorIssueLinkEl = document.querySelector(".error-issue-link");

  if (errContextMessage) {
    errorContextMessageEl.textContent = errContextMessage;
  } else {
    errorContextMessageEl.textContent = "";
  }
  if (err) {
    errorEl.classList.remove("d-none");
  } else {
    errorEl.classList.add("d-none");
  }
  if (
    err &&
    err.response &&
    err.response.headers &&
    err.response.headers.get("x-request-id")
  ) {
    let requestID = err.response.headers.get("x-request-id");
    errorReqIDEl.textContent = requestID;
    errorIssueLinkEl.href = `https://github.com/mozilla-services/dependency-observatory/issues/new?title=error making request&body=request id: ${requestID}`;
  } else {
    errorReqIDEl.textContent = "";
    errorIssueLinkEl.href = `https://github.com/mozilla-services/dependency-observatory/issues/new?title=error making request&body=request id: replaceme`;
  }
}

function updateSearchForm(disable) {
  if (disable) {
    console.debug("disabling search form");
    formFieldsetEls.forEach((fieldsetEl) =>
      fieldsetEl.setAttribute("disabled", "disabled")
    );
  } else {
    console.debug("enabling search form");
    formFieldsetEls.forEach((fieldsetEl) =>
      fieldsetEl.removeAttribute("disabled")
    );
  }
}

async function scanAndScorePackage(formDataObj) {
  console.debug("starting scan with data:", formDataObj);
  let startScanResponseJSON = await startScan(formDataObj);
  let scanID = startScanResponseJSON.id;
  console.log(
    `created scan with name: ${scanID} and URL: ${window.location.origin}/api/v1/scans/${scanID}`
  );
  return scanID;
}

function redirectToScanLogs(scanID) {
  let scanLogsURI = `/scans/${scanID}/logs`;
  console.log(
    `redirecting to tail logs at ${window.location.origin}${scanLogsURI}`
  );
  window.location.assign(scanLogsURI);
}

function onSubmit(event) {
  console.debug(`form submitted! timestamp: ${event.timeStamp}`);
  event.preventDefault();
  updateSearchError(null); // clear error display

  let formData = new FormData(formEl);
  let formDataObj = Object.fromEntries(formData);
  console.debug("have formdata", formDataObj);

  if (formDataObj.force_rescan === "on") {
    console.debug("skipping report check since rescan requested");
    scanAndScorePackage(formDataObj)
      .then(redirectToScanLogs)
      .catch((err) => {
        console.error(`error starting rescan: ${err}`);
        updateSearchError(err, "rescanning a package");
      });
  } else if (!formDataObj.package_version) {
    console.debug("skipping report check since package version not specified");
    scanAndScorePackage(formDataObj)
      .then(redirectToScanLogs)
      .catch((err) => {
        console.error(`error starting rescan: ${err}`);
        updateSearchError(err, "rescanning a package");
      });
  } else {
    updateSearchForm(true); // disable the search form
    checkReportExists(formData)
      .catch((err) => {
        updateSearchForm(false); // enable the search form
        console.error(`error checking report exists: ${err}`);
        updateSearchError(err, "checking a package report exists");
      })
      .then((response) => {
        updateSearchForm(false); // enable the search form

        if (response.status === 200) {
          // redirect to report if it exists
          console.debug(`report exists redirecting to ${response.url}`);
          window.location.assign(response.url);
          // } else if (response.status === 422) {
          //   // TODO: display the error message for malformed requests
          //   // updateSearchError(true, "checking a package report exists", response.headers.get("x-request-id"));
        } else if (response.status !== 404) {
          // something unexpected display an error for non-404 errors
          let err = new Error();
          err.response = response;
          updateSearchError(err, "checking a package report exists");
        } else {
          scanAndScorePackage(formDataObj)
            .then(redirectToScanLogs)
            .catch((err) => {
              console.error(`error starting scan: ${err}`);
              updateSearchError(err, "scanning a package");
            });
        }
      });
  }
}

window.addEventListener("DOMContentLoaded", (event) => {
  console.debug("DOM fully loaded and parsed");

  // bind
  formEl.addEventListener("submit", onSubmit);
});
