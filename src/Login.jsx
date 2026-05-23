import { useState } from "react"
import { useNavigate } from "react-router-dom"
import axios from "axios"

function Login() {
  const [storeId, setStoreId] = useState("")
  const [pin, setPin] = useState("")
  const [errorMessage, setErrorMessage] = useState(["", 0])
  const navigate = useNavigate()
  
  const handleStoreIdChange = (e) => {
        const numbers = e.target.value.replace(/\D/g, '')
        const formatted = `#${numbers.substring(0, 5)}`;
        setStoreId(formatted)
        setErrorMessage(["", 0])
    }

    const handleSubmit = (e) => {
      e.preventDefault()

      if (!storeId.trim()) {
        setErrorMessage(["Please enter a Store ID", 0])
        return
      }
      if (!pin.trim()) {
        setErrorMessage(["Please enter a Store ID", 1])
        return
      }
      if (storeId.length > 6 && storeId.length <= 1) {
        setErrorMessage(["Your store id must have more than 1 but less than 5 digits, you can find it on the receipt", 0])
        return
      }
      if (pin.length != 4) {
        setErrorMessage(["Your pin is not 4 digits, if you don't know the pin contact your manager", 1])
        return
      }

      // add leading zeros
      const paddedId = "#" + storeId.replace("#", "").padStart(5, "0")

      const data = {
        storeId: paddedId,
        pin: pin
      }
      axios.post("/api/login", data).then((res) => {
        console.log("msg: ", res.data.message)
        const token = res.data.token;
        localStorage.setItem("token", token)
        navigate("/dashboard")
      }).catch((err) => {
        console.log(err)
        console.log(err.response.data.message)
        setErrorMessage([err.response.data.message, "both"])
      })
    }

    return <div className="app">
        
        <form onSubmit={handleSubmit} className="input-form">
        <header className="header">
          <h1>Login to your store</h1>
        </header>
          <div className="input-group vertical-input-group">
            <input
              autoFocus
              type="text"
              value={storeId}
              onChange={handleStoreIdChange}
              placeholder="Store ID (e.g. #12345)"
              className={`code-input ${( errorMessage[1] == 0 && errorMessage[0]) || errorMessage[1] == "both" ? 'error' : ''}`}
              id="storeId"
            />
            <input
              type="password"
              value={pin}
              onChange={(e) => {setPin(e.target.value)}}
              placeholder="Pin (request from your manager)"
              className={`code-input ${( errorMessage[1] == 1 && errorMessage[0]) || errorMessage[1] == "both" ? 'error' : ''}`}
              id="pin"
              pattern="\d*"
              maxLength={4}
            />
            <button type="submit" className="add-button">
              Login
            </button>
          </div>
          {errorMessage[0] && <div className="error-message">{errorMessage[0]}</div>}
        </form>
    </div>
}

export default Login