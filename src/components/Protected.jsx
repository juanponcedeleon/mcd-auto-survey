import axios from "axios"
import { useEffect } from "react"
import { useNavigate } from "react-router-dom"

export default function Protected({ setVerified }) {
    const navigate = useNavigate()

    useEffect(() => {
        const token = localStorage.getItem("token")
        if (!token) {
            console.log("no token")
            navigate("/login")
        }

        axios.get("/api/verify-user", {
            headers: { Authorization: `Bearer ${token}` }
        }).then((res) => {
            console.log("this user is verified")
            setVerified(true);
        }).catch((err) => {
            console.log("no bueno")
            navigate("/login")
        })
    }, [])

    return <></>
}